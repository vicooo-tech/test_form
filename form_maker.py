import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st


# -----------------------------
# Load JSON files
# -----------------------------

def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


schema = load_json("jason_form_schema.json")
translations = load_json("translations.json")


# -----------------------------
# Translation helper
# -----------------------------

def t(key, language):
    """
    Translate a translation key into the selected language.
    Falls back to default language, then key itself.
    """
    item = translations.get(key, {})

    if not item:
        return key

    return (
        item.get(language)
        or item.get(schema["default_language"])
        or key
    )


# -----------------------------
# Helpers
# -----------------------------

def generate_system_value(field):
    """
    Generate automatic values for hidden/system fields.
    """
    strategy = field.get("generation_strategy")

    if strategy == "uuid":
        return str(uuid.uuid4())

    if strategy == "current_timestamp":
        timezone = field.get("timezone", "Europe/Zurich")
        return datetime.now(ZoneInfo(timezone)).isoformat()

    return None


def set_nested_value(data, dotted_key, value):
    """
    Convert database_key like 'reporter.name'
    into nested JSON:
    {
      "reporter": {
        "name": value
      }
    }
    """
    keys = dotted_key.split(".")
    current = data

    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    current[keys[-1]] = value


def is_empty(value):
    """
    Check whether a field value should count as missing.
    """
    if value is None:
        return True

    if value == "":
        return True

    if value == []:
        return True

    return False


def get_option_labels(field, language):
    """
    Return displayed labels and internal values for choice fields.
    """
    labels = []
    values = []

    for option in field.get("options", []):
        labels.append(t(option["label_key"], language))
        values.append(option["value"])

    return labels, values


def get_department_hint(schema, answers):
    """
    Finds the department_hint from the selected damage category.
    """
    selected_category = answers.get("damage_category")

    if not selected_category:
        return None

    for section in schema["sections"]:
        for field in section.get("fields", []):
            if field["id"] == "damage_category":
                for option in field.get("options", []):
                    if option["value"] == selected_category:
                        return option.get("department_hint")

    return None


def create_google_maps_link(coordinates):
    """
    Creates a Google Maps URL from coordinates text.
    Expected format: '47.3769, 8.5417'
    """
    if not coordinates:
        return None

    cleaned = coordinates.replace(" ", "")
    return f"https://www.google.com/maps?q={cleaned}"


# -----------------------------
# Streamlit page setup
# -----------------------------

st.set_page_config(
    page_title="Zurich Damage Report",
    page_icon="🛠️",
    layout="centered"
)

st.title("Zurich Damage Report")
st.caption("Generated automatically from JSON schema")


# -----------------------------
# Language selection
# -----------------------------

language = st.selectbox(
    "Language / Sprache / Lingua / Langue",
    schema["supported_languages"],
    index=schema["supported_languages"].index(schema["default_language"])
)

st.divider()


# -----------------------------
# Render form
# -----------------------------

raw_answers = {}
uploaded_files = {}

with st.form("damage_report_form"):
    for section in schema["sections"]:

        # Do not display metadata/system fields
        if section["id"] == "metadata":
            for field in section.get("fields", []):
                raw_answers[field["id"]] = generate_system_value(field)
            continue

        st.subheader(t(section["title_key"], language))

        for field in section.get("fields", []):
            field_id = field["id"]
            field_type = field["type"]
            required = field.get("required", False)
            label = t(field["label_key"], language)

            if required:
                label = label + " *"

            placeholder = None
            if "placeholder_key" in field:
                placeholder = t(field["placeholder_key"], language)

            # -----------------------------
            # Text input
            # -----------------------------
            if field_type == "text":
                raw_answers[field_id] = st.text_input(
                    label,
                    placeholder=placeholder or ""
                )

            # -----------------------------
            # Textarea
            # -----------------------------
            elif field_type == "textarea":
                raw_answers[field_id] = st.text_area(
                    label,
                    placeholder=placeholder or ""
                )

            # -----------------------------
            # Single choice
            # -----------------------------
            elif field_type == "single_choice":
                labels, values = get_option_labels(field, language)

                display_options = [""] + labels

                selected_label = st.selectbox(
                    label,
                    display_options,
                    index=0
                )

                if selected_label == "":
                    raw_answers[field_id] = ""
                else:
                    selected_index = labels.index(selected_label)
                    raw_answers[field_id] = values[selected_index]

            # -----------------------------
            # Multiple choice
            # -----------------------------
            elif field_type == "multiple_choice":
                labels, values = get_option_labels(field, language)

                selected_labels = st.multiselect(
                    label,
                    labels
                )

                selected_values = [
                    values[labels.index(selected_label)]
                    for selected_label in selected_labels
                ]

                raw_answers[field_id] = selected_values

            # -----------------------------
            # File upload
            # -----------------------------
            elif field_type == "file":
                max_files = field.get("max_files", 1)
                accept = field.get("accept", ["image/jpeg", "image/png", "image/webp"])

                # Convert MIME types to Streamlit extensions
                file_types = []
                for mime_type in accept:
                    if mime_type == "image/jpeg":
                        file_types.extend(["jpg", "jpeg"])
                    elif mime_type == "image/png":
                        file_types.append("png")
                    elif mime_type == "image/webp":
                        file_types.append("webp")

                files = st.file_uploader(
                    label,
                    type=file_types,
                    accept_multiple_files=max_files > 1
                )

                raw_answers[field_id] = files
                uploaded_files[field_id] = files

            # -----------------------------
            # Date
            # -----------------------------
            elif field_type == "date":
                raw_answers[field_id] = st.date_input(label)

            # -----------------------------
            # Location / coordinates
            # -----------------------------
            elif field_type == "location":
                raw_answers[field_id] = st.text_input(
                    label,
                    placeholder=placeholder or "47.3769, 8.5417"
                )

            # -----------------------------
            # Hidden
            # -----------------------------
            elif field_type == "hidden":
                raw_answers[field_id] = generate_system_value(field)

            else:
                st.warning(f"Unsupported field type: {field_type}")

        st.write("")

    submitted = st.form_submit_button("Submit report")


# -----------------------------
# Handle submission
# -----------------------------

if submitted:
    missing_fields = []

    for section in schema["sections"]:
        for field in section.get("fields", []):
            field_id = field["id"]

            if field.get("required", False):
                value = raw_answers.get(field_id)

                if is_empty(value):
                    if "label_key" in field:
                        missing_fields.append(t(field["label_key"], language))
                    else:
                        missing_fields.append(field_id)

    if missing_fields:
        st.error("Please complete all required fields.")

        for missing in missing_fields:
            st.write(f"- {missing}")

    else:
        report = {}

        # Map raw answers into nested database structure
        for section in schema["sections"]:
            for field in section.get("fields", []):
                field_id = field["id"]
                database_key = field.get("database_key")

                if not database_key:
                    continue

                value = raw_answers.get(field_id)

                # For uploaded files, store only file names for now
                # Later, replace this with S3 URLs
                if field["type"] == "file":
                    if isinstance(value, list):
                        value = [file.name for file in value]
                    elif value is not None:
                        value = [value.name]
                    else:
                        value = []

                # Convert date object to string
                if field["type"] == "date" and value is not None:
                    value = value.isoformat()

                set_nested_value(report, database_key, value)

        # Add selected language
        set_nested_value(report, "metadata.language", language)

        # Add initial status
        set_nested_value(report, "metadata.status", "new")

        # Add department hint
        department_hint = get_department_hint(schema, raw_answers)
        set_nested_value(report, "classification.responsible_department", department_hint)

        # Add map link
        coordinates = raw_answers.get("coordinates")
        map_link = create_google_maps_link(coordinates)
        set_nested_value(report, "location.map_link", map_link)

        st.success("Report created successfully.")

        st.subheader("Generated report JSON")
        st.json(report)

        st.subheader("Human-readable preview")

        metadata = report.get("metadata", {})
        reporter = report.get("reporter", {})
        location = report.get("location", {})
        damage = report.get("damage", {})
        media = report.get("media", {})
        classification = report.get("classification", {})

        st.markdown(f"""
### Damage Report

**Report ID:** {metadata.get("report_id", "-")}  
**Reported at:** {metadata.get("reported_at", "-")}  
**Status:** {metadata.get("status", "-")}  
**Responsible department:** {classification.get("responsible_department", "-")}

---

### Location

**Coordinates:** {location.get("coordinates", "-")}  
**Map:** {location.get("map_link", "-")}

---

### Damage Details

**Category:** {damage.get("category", "-")}  
**Title:** {damage.get("title", "-")}  

**Description:**  
{damage.get("description", "-")}

---

### Photos

{media.get("photos", "-")}

---

### Reporter

**Name:** {reporter.get("name", "-")}  
**Preferred contact:** {reporter.get("preferred_contact", "-")}  
**Contact:** {reporter.get("contact", "-")}
""")

        # Download report as JSON
        st.download_button(
            label="Download report JSON",
            data=json.dumps(report, indent=2, ensure_ascii=False),
            file_name=f"{metadata.get('report_id', 'damage_report')}.json",
            mime="application/json"
        )
