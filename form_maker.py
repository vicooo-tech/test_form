import base64
import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import streamlit as st
from streamlit_js_eval import get_geolocation


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
    item = translations.get(key, {})

    if not item:
        return key

    return (
        item.get(language)
        or item.get(schema.get("default_language", "de"))
        or item.get("en")
        or key
    )


# -----------------------------
# AWS POST helper
# -----------------------------

def send_report_to_aws(report):
    aws_form_url = st.secrets.get("AWS_FORM_URL")
    aws_api_key = st.secrets.get("AWS_API_KEY")

    if not aws_form_url:
        return {
            "success": False,
            "error": "Missing AWS_FORM_URL in Streamlit secrets."
        }

    if not aws_api_key:
        return {
            "success": False,
            "error": "Missing AWS_API_KEY in Streamlit secrets."
        }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": aws_api_key
    }

    try:
        response = requests.post(
            aws_form_url,
            headers=headers,
            json=report,
            timeout=30
        )

        if 200 <= response.status_code < 300:
            try:
                response_data = response.json()
            except ValueError:
                response_data = response.text

            return {
                "success": True,
                "status_code": response.status_code,
                "response": response_data
            }

        return {
            "success": False,
            "status_code": response.status_code,
            "error": response.text
        }

    except requests.exceptions.RequestException as error:
        return {
            "success": False,
            "error": str(error)
        }


# -----------------------------
# Helpers
# -----------------------------

def generate_system_value(field):
    strategy = field.get("generation_strategy")

    if strategy == "uuid":
        return str(uuid.uuid4())

    if strategy == "current_timestamp":
        timezone = field.get("timezone", "Europe/Zurich")
        return datetime.now(ZoneInfo(timezone)).isoformat()

    return None


def set_nested_value(data, dotted_key, value):
    keys = dotted_key.split(".")
    current = data

    for key in keys[:-1]:
        if key not in current:
            current[key] = {}

        current = current[key]

    current[keys[-1]] = value


def is_empty(value):
    if value is None:
        return True

    if value == "":
        return True

    if value == []:
        return True

    return False


def get_option_labels(field, language):
    labels = []
    values = []

    for option in field.get("options", []):
        labels.append(t(option["label_key"], language))
        values.append(option["value"])

    return labels, values


def get_department_hint(schema, answers):
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
    if not coordinates:
        return None

    cleaned = coordinates.replace(" ", "")
    return f"https://www.google.com/maps?q={cleaned}"


def mime_to_extensions(accept_list):
    file_types = []

    for mime_type in accept_list:
        if mime_type == "image/jpeg":
            file_types.extend(["jpg", "jpeg"])
        elif mime_type == "image/png":
            file_types.append("png")
        elif mime_type == "image/webp":
            file_types.append("webp")
        elif mime_type == "application/pdf":
            file_types.append("pdf")

    return file_types


def encode_uploaded_file(uploaded_file):
    file_bytes = uploaded_file.getvalue()
    encoded = base64.b64encode(file_bytes).decode("utf-8")

    return {
        "filename": uploaded_file.name,
        "content_type": uploaded_file.type,
        "size_bytes": uploaded_file.size,
        "base64": encoded
    }


# -----------------------------
# Streamlit page setup
# -----------------------------

st.set_page_config(
    page_title="Zurich Damage Report",
    page_icon="🛠️",
    layout="centered"
)


# -----------------------------
# Language selector top right
# -----------------------------

language_labels = {
    "de": "Deutsch",
    "en": "English",
    "it": "Italiano",
    "fr": "Français"
}

top_left, top_right = st.columns([3, 1])

with top_right:
    language = st.selectbox(
        "Language",
        options=schema["supported_languages"],
        format_func=lambda code: language_labels.get(code, code),
        index=schema["supported_languages"].index(schema["default_language"]),
        key="selected_language",
        label_visibility="collapsed"
    )


# -----------------------------
# App title
# -----------------------------

st.title(t("app.title", language))
st.caption(t("app.caption", language))

st.divider()


# -----------------------------
# Geolocation outside the form
# -----------------------------

coordinates_widget_key = f"{language}_coordinates"

st.subheader(t("section.location.title", language))
st.write(t("field.coordinates.label", language))

try:
    location_data = get_geolocation()
except Exception:
    location_data = None
    st.warning(t("field.coordinates.manual_fallback", language))

if location_data:
    latitude = location_data["coords"]["latitude"]
    longitude = location_data["coords"]["longitude"]

    coordinates_value = f"{latitude}, {longitude}"

    if st.session_state.get(coordinates_widget_key) != coordinates_value:
        st.session_state[coordinates_widget_key] = coordinates_value
        st.rerun()

    st.success(f"Location detected: {coordinates_value}")

st.divider()


# -----------------------------
# Render form
# -----------------------------

raw_answers = {}

with st.form("damage_report_form"):
    for section in schema["sections"]:

        # Do not display metadata/system fields
        if section["id"] == "metadata":
            for field in section.get("fields", []):
                raw_answers[field["id"]] = generate_system_value(field)
            continue

        # Location section title is already shown above
        if section["id"] != "location":
            st.subheader(t(section["title_key"], language))

        for field in section.get("fields", []):
            field_id = field["id"]
            field_type = field["type"]
            required = field.get("required", False)

            if field_type == "hidden":
                raw_answers[field_id] = generate_system_value(field)
                continue

            label = t(field["label_key"], language)

            if required:
                label = label + " *"

            placeholder = ""
            if "placeholder_key" in field:
                placeholder = t(field["placeholder_key"], language)

            widget_key = f"{language}_{field_id}"

            # -----------------------------
            # Text input
            # -----------------------------
            if field_type == "text":
                raw_answers[field_id] = st.text_input(
                    label,
                    placeholder=placeholder,
                    key=widget_key
                )

            # -----------------------------
            # Textarea
            # -----------------------------
            elif field_type == "textarea":
                raw_answers[field_id] = st.text_area(
                    label,
                    placeholder=placeholder,
                    key=widget_key
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
                    index=0,
                    key=widget_key
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
                    labels,
                    key=widget_key
                )

                selected_values = [
                    values[labels.index(selected_label)]
                    for selected_label in selected_labels
                ]

                raw_answers[field_id] = selected_values

            # -----------------------------
            # Date
            # -----------------------------
            elif field_type == "date":
                raw_answers[field_id] = st.date_input(
                    label,
                    key=widget_key
                )

            # -----------------------------
            # Location / coordinates
            # -----------------------------
            elif field_type == "location":
                raw_answers[field_id] = st.text_input(
                    label,
                    placeholder=placeholder or "47.3769, 8.5417",
                    key=widget_key
                )

            # -----------------------------
            # File upload
            # -----------------------------
            elif field_type == "file":
                max_files = field.get("max_files", 1)
                accept = field.get("accept", ["image/jpeg", "image/png", "image/webp"])
                file_types = mime_to_extensions(accept)

                uploaded = st.file_uploader(
                    label,
                    type=file_types,
                    accept_multiple_files=max_files > 1,
                    key=widget_key
                )

                raw_answers[field_id] = uploaded

            else:
                st.warning(f"Unsupported field type: {field_type}")

        st.write("")

    submitted = st.form_submit_button(t("button.submit_report", language))


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
                field_type = field.get("type")
                database_key = field.get("database_key")

                if not database_key:
                    continue

                value = raw_answers.get(field_id)

                # Convert date object to string
                if field_type == "date" and value is not None:
                    value = value.isoformat()

                # Convert uploaded files to JSON-safe base64 objects
                if field_type == "file":
                    if isinstance(value, list):
                        value = [encode_uploaded_file(file) for file in value]
                    elif value is not None:
                        value = [encode_uploaded_file(value)]
                    else:
                        value = []

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

        aws_result = send_report_to_aws(report)

        if aws_result["success"]:
            st.success("Report sent to AWS successfully.")
        else:
            st.error("Report could not be sent to AWS.")
            st.write(aws_result.get("error"))

        st.subheader("Generated report JSON")
        st.json(report)

        st.subheader("Human-readable preview")

        metadata = report.get("metadata", {})
        reporter = report.get("reporter", {})
        location = report.get("location", {})
        damage = report.get("damage", {})
        media = report.get("media", {})
        classification = report.get("classification", {})

        photo_names = []
        for photo in media.get("photos", []):
            if isinstance(photo, dict):
                photo_names.append(photo.get("filename", "-"))

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

{", ".join(photo_names) if photo_names else "-"}

---

### Reporter

**Name:** {reporter.get("name", "-")}  
**Preferred contact:** {reporter.get("preferred_contact", "-")}  
**Contact:** {reporter.get("contact", "-")}
""")

        st.download_button(
            label="Download report JSON",
            data=json.dumps(report, indent=2, ensure_ascii=False),
            file_name=f"{metadata.get('report_id', 'damage_report')}.json",
            mime="application/json"
        )
