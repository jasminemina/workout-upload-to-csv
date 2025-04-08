import streamlit as st
from PIL import Image
import pytesseract # Requires Tesseract installation
import io
import re
import csv
import pandas as pd # Optional: useful for data handling & display

# --- Optional: Move these functions to helpers.py ---

def perform_ocr(image_bytes):
    """Performs OCR on the uploaded image bytes."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Optional: Add image preprocessing here if needed (grayscale, thresholding)
        text = pytesseract.image_to_string(img)
        st.write("### Extracted Text (Debug):") # Show OCR output for debugging
        st.text_area("OCR Output", text, height=200)
        return text
    except Exception as e:
        st.error(f"OCR Error: {e}")
        st.warning("Ensure Tesseract is installed and configured correctly if running locally.")
        st.warning("On Streamlit Community Cloud, ensure `packages.txt` includes tesseract-ocr.")
        return None

def parse_workout_text(text):
    """
    Parses the OCR text to extract workout details.
    *** THIS IS THE MOST COMPLEX PART AND HIGHLY DEPENDENT ON SCREENSHOT FORMAT ***
    *** You WILL need to write specific Regex/logic based on YOUR screenshots ***
    """
    exercises = []
    workout_date = "Unknown Date"
    all_equipment = set()

    # --- Placeholder Logic (Needs MAJOR Refinement) ---
    # 1. Find Date (Example: look for patterns like "Mon, Apr 7" or "April 7, 2025")
    date_match = re.search(r"(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}(?:,\s+\d{4})?)", text)
    if date_match:
        # Use current year if year not found, adjust date based on current time
        # For robustness, consider using dateutil.parser
        workout_date = date_match.group(1)
        # If year is missing, append the current year (adjust as needed)
        if not re.search(r',\s*\d{4}', workout_date):
             from datetime import datetime
             workout_date += f", {datetime.now().year}"

    # 2. Find Exercises (Example: look for lines starting A1., B2., etc. or specific keywords)
    #    This requires analyzing YOUR TrueCoach format.
    lines = text.split('\n')
    current_exercise = None
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # Example: Detect exercise start (adjust pattern significantly!)
        exercise_match = re.match(r"^([A-Z]\d+?\.?\s+)(.*)", line)
        if exercise_match:
            if current_exercise: # Save previous exercise
                 exercises.append(current_exercise)
            current_exercise = {
                "Exercise": exercise_match.group(2).strip(),
                "Equipment": "Unknown", # Placeholder
                "Weight": "N/A",      # Placeholder
                "Sets": "N/A",        # Placeholder
                "Reps": "N/A",        # Placeholder
                "Notes": "",          # Placeholder
                "Muscle Group": "Unknown", # Placeholder
                "Demo": "",           # Placeholder
            }
            # Basic equipment guess (add more keywords)
            if "DB" in current_exercise["Exercise"] or "Dumbbell" in current_exercise["Exercise"]:
                current_exercise["Equipment"] = "Dumbbells"
                all_equipment.add("Dumbbells")
            elif "BB" in current_exercise["Exercise"] or "Barbell" in current_exercise["Exercise"]:
                 current_exercise["Equipment"] = "Barbell"
                 all_equipment.add("Barbell")
            # ... add more equipment detection ...

        elif current_exercise:
             # Example: Detect Sets/Reps/Weight (adjust pattern significantly!)
             set_rep_match = re.search(r"(\d+)\s*(?:sets?|x)\s*(\d+)\s*reps?", line, re.IGNORECASE)
             weight_match = re.search(r"@\s*(\d+\.?\d*)\s*(lbs|kg)?", line, re.IGNORECASE)
             bw_match = re.search(r"BW|Bodyweight", line, re.IGNORECASE)

             if set_rep_match:
                 current_exercise["Sets"] = set_rep_match.group(1)
                 current_exercise["Reps"] = set_rep_match.group(2)
             if weight_match:
                 weight_val = float(weight_match.group(1))
                 unit = weight_match.group(2) if weight_match.group(2) else "lbs" # Default unit
                 # *** Handle the complex weight formatting requirement here ***
                 # This is tricky. You might need context (like equipment type)
                 if current_exercise["Equipment"] == "Dumbbells": # Example assumption
                     current_exercise["Weight"] = f"{weight_val * 2}{unit} total, {weight_val}{unit} dumbbells in each hand"
                 else:
                     current_exercise["Weight"] = f"{weight_val} {unit}"
             elif bw_match:
                 current_exercise["Weight"] = "Bodyweight"
             else:
                # Assume other lines are notes (simple approach)
                 if not set_rep_match and not weight_match:
                     current_exercise["Notes"] += line + " "


    if current_exercise: # Add the last exercise
        exercises.append(current_exercise)

    # Refine notes (remove extra spaces)
    for ex in exercises:
        ex["Notes"] = ex["Notes"].strip()

    # --- End Placeholder Logic ---

    if not exercises:
        st.warning("Could not parse exercises. The OCR text might be unclear or the format unexpected. Check the debug output above.")


    return exercises, workout_date, list(all_equipment)


def enrich_data(exercises):
    """Adds muscle groups, demo links, and summary."""
    # --- Placeholder Logic ---
    # 1. Load muscle map (from dict, JSON, etc.)
    # Example:
    muscle_map = {
         "Squat": "Quads, Glutes, Hamstrings", # Add many more
         "Bench Press": "Chest, Triceps, Shoulders"
     }
    for ex in exercises:
         # Basic lookup, needs better matching (lowercase, remove details)
         simple_name = ex["Exercise"].split('-')[0].strip().title() # Very basic cleanup
         ex["Muscle Group"] = muscle_map.get(simple_name, "Unknown")
         # 2. Add Demo Link (Requires YouTube API - complex setup with keys)
         # For simplicity, using a placeholder search link
         query = ex['Exercise'].replace(' ','+')
         ex["Demo"] = f"https://www.youtube.com/results?search_query={query}+demonstration"

    # 3. Generate Summary (Simple keyword-based)
    summary_words = []
    if any("Squat" in ex["Exercise"] or "Leg Press" in ex["Exercise"] for ex in exercises): summary_words.append("Leg Day")
    if any("Bench" in ex["Exercise"] or "Push Up" in ex["Exercise"] for ex in exercises): summary_words.append("Push Focus")
    if any("Row" in ex["Exercise"] or "Pull Down" in ex["Exercise"] for ex in exercises): summary_words.append("Pull Focus")
    if not summary_words: summary_words.append("General Workout")

    # Add user's specific request phrase if relevant (requires more logic)
    # if pain_syndrome_detected: summary_words.append("addressing patellofemoral pain")

    summary = ", ".join(summary_words)[:50] # Limit length

    return exercises, summary


def create_csv_string(summary, total_equipment_list, enriched_data, workout_date):
    """Generates the CSV data as a string."""
    output = io.StringIO()
    fieldnames = ["Summary", "Total Equipment", "Exercise", "Equipment", "Weight", "Sets", "Reps", "Notes", "Muscle Group", "Demo", "Date"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)

    writer.writeheader()
    total_equipment_str = ", ".join(total_equipment_list) if total_equipment_list else "None"

    if not enriched_data: # Write only header if no data parsed
        st.warning("No exercises parsed to write to CSV.")
        return output.getvalue()

    for exercise in enriched_data:
        row = {
            "Summary": summary,
            "Total Equipment": total_equipment_str,
            "Exercise": exercise.get("Exercise", ""),
            "Equipment": exercise.get("Equipment", ""),
            "Weight": exercise.get("Weight", ""),
            "Sets": exercise.get("Sets", ""),
            "Reps": exercise.get("Reps", ""),
            "Notes": exercise.get("Notes", ""),
            "Muscle Group": exercise.get("Muscle Group", ""),
            "Demo": exercise.get("Demo", ""),
            "Date": workout_date
        }
        writer.writerow(row)

    return output.getvalue()

# --- Streamlit App UI ---

st.set_page_config(layout="wide")
st.title("🏋️ TrueCoach Screenshot to CSV Converter")

st.markdown("""
Upload a screenshot of your workout from the TrueCoach app.
The app will attempt to extract the details using OCR and generate a downloadable CSV file.

**Disclaimer:** This tool relies on OCR and pattern matching. Accuracy depends heavily on the screenshot's clarity and format. The parsing logic is basic and may need significant adjustments for your specific TrueCoach layout.
""")

uploaded_file = st.file_uploader("Choose a screenshot...", type=["png", "jpg", "jpeg", "bmp", "webp"])

if uploaded_file is not None:
    st.image(uploaded_file, caption='Uploaded Screenshot.', use_column_width=True)
    st.info("Processing screenshot... This may take a moment.")

    image_bytes = uploaded_file.getvalue()

    # Use columns for better layout
    col1, col2 = st.columns(2)

    with col1:
        with st.spinner('Performing OCR...'):
            extracted_text = perform_ocr(image_bytes)

    if extracted_text:
        with col2:
            with st.spinner('Parsing and Enriching Data...'):
                # Parsing
                parsed_exercises, workout_date, all_equipment = parse_workout_text(extracted_text)

                if parsed_exercises: # Proceed only if parsing found something
                    # Enrichment
                    enriched_data, summary = enrich_data(parsed_exercises) # Pass parsed data

                    # CSV Generation
                    csv_data = create_csv_string(summary, all_equipment, enriched_data, workout_date)

                    st.success("Processing Complete!")

                    # Display Parsed Data (Optional but helpful)
                    st.write("### Parsed Workout Data (Preview):")
                    df = pd.DataFrame(enriched_data)
                    st.dataframe(df[['Exercise', 'Equipment', 'Weight', 'Sets', 'Reps', 'Notes', 'Muscle Group']])

                    # Download Button
                    st.download_button(
                        label="📥 Download Workout CSV",
                        data=csv_data,
                        file_name=f"truecoach_workout_{workout_date.replace(', ','_').replace(' ','_')}.csv",
                        mime='text/csv',
                    )
                else:
                     st.error("Failed to parse exercise details from the text.")
