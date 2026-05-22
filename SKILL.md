---
name: zurich-damage-report
description: "Submit a Zurich city damage report (potholes, graffiti, streetlights, etc.) to the demo DynamoDB table via API Gateway."
metadata:
  {
    "openclaw":
      {
        "emoji": "🦺",
        "requires": { "bins": ["curl"] },
      },
  }
---

# Zurich Damage Report

Use this skill when the user wants to file a city damage report for Zurich (potholes, broken streetlights, graffiti, illegal dumping, drainage issues, park/tree damage, public transport infrastructure).

## Workflow

1. Collect all required fields from the user through conversation
2. Auto-generate `dynamodbkey`, `report_id`, and `reported_at`
3. POST the record to the API Gateway endpoint

## Required Fields

- `reporter_name`: Full name of the person reporting
- `preferred_contact`: One of: `whatsapp`, `phone`, `email`
- `contact_value`: The actual phone number or email address
- `latitude`: GPS latitude (decimal number, e.g. 47.3769)
- `longitude`: GPS longitude (decimal number, e.g. 8.5417)
- `damage_category`: One of: `road_sidewalk_damage`, `streetlight_problem`, `trash_or_dumping`, `graffiti`, `water_or_drainage`, `park_or_tree`, `public_transport`
- `damage_title`: Short one-sentence title describing the damage
- `damage_description`: Detailed description of the damage

## Optional Fields

- `already_reported`: `yes` / `no` / `unknown` (default: `unknown`)
- `additional_notes`: Any extra context
- `photos`: List of S3 URLs for uploaded photos (can be empty)

## Submitting the Report

Once all required fields are collected, build the JSON record and submit it:

```bash
# Generate UUIDs and timestamp
DYNAMODBKEY=$(uuidgen | tr '[:upper:]' '[:lower:]')
REPORT_ID=$(uuidgen | tr '[:upper:]' '[:lower:]')
REPORTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%S+02:00")

# Submit via curl
curl -s -X POST "https://qpulsxpdci.execute-api.us-east-1.amazonaws.com/llm" \
  -H "Content-Type: application/json" \
  -H "x-api-key: Jj9xJMshZJ8I2RN7JCvKe53MT7PwmCjq9pHupXJl" \
  -d '{
    "dynamodbkey":   "'"$DYNAMODBKEY"'",
    "form_id":       "zurich_damage_report",
    "form_version":  "1.0",
    "metadata": {
      "report_id":        "'"$REPORT_ID"'",
      "reported_at":      "'"$REPORTED_AT"'",
      "already_reported": "unknown",
      "additional_notes": ""
    },
    "reporter": {
      "name":              "REPORTER_NAME",
      "preferred_contact": "PREFERRED_CONTACT",
      "contact":           "CONTACT_VALUE"
    },
    "location": {
      "coordinates": {
        "latitude":  LATITUDE,
        "longitude": LONGITUDE
      }
    },
    "damage": {
      "category":    "DAMAGE_CATEGORY",
      "title":       "DAMAGE_TITLE",
      "description": "DAMAGE_DESCRIPTION"
    },
    "media": {
      "photos": []
    }
  }'
```

Replace the placeholder values with the actual collected field values before running.

## Success Response

After a successful submission, confirm to the user:

```
✅ Damage report submitted successfully!
Report ID: <report_id>
Record Key: <dynamodbkey>
Category: <damage_category>
Submitted at: <reported_at>
```

## Error Handling

- If the API returns a non-2xx status, show the error and ask the user to retry
- If a required field is missing, ask the user for it before submitting
- If coordinates are not provided, ask the user to share their location or enter them manually

## Notes

- `dynamodbkey` and `report_id` are always auto-generated UUIDs — never ask the user for these
- `reported_at` is always the current timestamp in Europe/Zurich timezone
- The full record is stored as a single JSON object in the `demo` DynamoDB table
- Photos are optional — if not provided, submit with an empty array
