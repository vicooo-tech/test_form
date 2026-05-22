# 🦺 Zurich Damage Report — AI-Powered City Infrastructure Reporting

> Report potholes, broken streetlights, graffiti, and more — just by chatting.

## The Problem

Reporting city infrastructure damage in Zurich is slow and fragmented. Citizens have to find the right department, fill out long web forms, and never know if their report was received. Most damage goes unreported.

## The Solution

An AI agent that turns a natural conversation into a structured damage report — submitted instantly to a city database, from any device, in any language.

You just chat. The agent does the rest.

```
You:   There's a huge pothole on Bahnhofstrasse near the tram stop
Agent: Got it. What's your name and preferred contact method?
You:   Pau, reach me on WhatsApp at +41 79 000 0000
Agent: Thanks! Can you share the GPS coordinates or describe the location?
...
Agent: ✅ Report submitted. Report ID: 8f3a2c1d | Key: 9e4b7f2a
```

---

## Architecture

```
User (any device)
    │
    ▼
OpenClaw Gateway (local Mac / self-hosted --> futre: AWS hosted for scalability)
    │
    ├──► Amazon Bedrock (AWS Account 1, us-west-2)
    │         Claude Sonnet 4.6 — natural language understanding
    │
    └──► API Gateway (AWS Account 2, us-east-1)
              │
              ▼
         DynamoDB — table: demo
              Structured damage report stored as JSON
```

**Two AWS accounts:**
- **Account 1** — Amazon Bedrock for AI inference (Claude Sonnet 4.6 via inference profile)
- **Account 2** — API Gateway + DynamoDB for data storage

**OpenClaw** runs locally on a Mac as a self-hosted AI gateway. It connects to Bedrock for intelligence and uses a custom skill (`/damage_report`) to collect and submit reports.

---

## What Was Built

### OpenClaw Skill — `/damage_report`

A custom skill that:
- Guides the user through all required fields via natural conversation
- Auto-generates UUIDs and timestamps
- Validates required fields before submitting
- POSTs the structured JSON record to the API Gateway endpoint
- Confirms submission with report ID and database key

### Data Schema

Each report is stored as a single JSON document in DynamoDB:

```json
{
  "dynamodbkey": "uuid",
  "form_id": "zurich_damage_report",
  "form_version": "1.0",
  "metadata": {
    "report_id": "uuid",
    "reported_at": "2026-05-22T10:30:00+02:00",
    "already_reported": "no",
    "additional_notes": ""
  },
  "reporter": {
    "name": "Pau",
    "preferred_contact": "whatsapp",
    "contact": "+41 79 000 0000"
  },
  "location": {
    "coordinates": {
      "latitude": 47.3769,
      "longitude": 8.5417
    }
  },
  "damage": {
    "category": "road_sidewalk_damage",
    "title": "Large pothole on Bahnhofstrasse",
    "description": "Pothole ~30cm wide near the tram stop, visible since last week."
  },
  "media": {
    "photos": []
  }
}
```

### Damage Categories

| Value | Description | Department |
|-------|-------------|------------|
| `road_sidewalk_damage` | Road or sidewalk damage | Road maintenance |
| `streetlight_problem` | Broken streetlight | Public lighting |
| `trash_or_dumping` | Illegal dumping | Waste management |
| `graffiti` | Graffiti | Cleaning |
| `water_or_drainage` | Drainage issue | Water department |
| `park_or_tree` | Park or tree damage | Parks & green spaces |
| `public_transport` | Transport infrastructure | Public transport |

---

## Setup Guide

### Prerequisites

- macOS with Homebrew
- [OpenClaw](https://openclaw.ai) installed (`brew install openclaw`)
- AWS account with Amazon Bedrock access (Claude Sonnet 4.6 enabled in us-west-2)
- AWS account with API Gateway + DynamoDB (`demo` table, partition key: `dynamodbkey`)

---

### 1. Configure OpenClaw

```bash
openclaw configure
```

Follow the wizard: local gateway, LAN bind, token auth.

---

### 2. Install the Bedrock Plugin

```bash
openclaw plugins install @openclaw/amazon-bedrock-provider
```

---

### 3. Configure Bedrock in `~/.openclaw/openclaw.json`

Add to the `plugins.entries` section:

```json
"amazon-bedrock": {
  "enabled": true,
  "config": {
    "discovery": {
      "enabled": true,
      "region": "us-west-2",
      "providerFilter": ["anthropic", "amazon", "meta"],
      "refreshInterval": 3600,
      "defaultContextWindow": 200000,
      "defaultMaxTokens": 4096
    }
  }
}
```

---

### 4. Inject AWS Credentials into the Gateway Service

The gateway runs as a launchd service and doesn't inherit terminal environment variables. Credentials must be written to the env file:

```bash
openclaw gateway stop

sed -i '' '/^export AWS/d' ~/.openclaw/service-env/ai.openclaw.gateway.env

cat >> ~/.openclaw/service-env/ai.openclaw.gateway.env << 'ENVEOF'
export AWS_ACCESS_KEY_ID="YOUR_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="YOUR_SECRET_ACCESS_KEY"
export AWS_SESSION_TOKEN="YOUR_SESSION_TOKEN"
export AWS_REGION=us-west-2
export AWS_DEFAULT_REGION=us-west-2
ENVEOF

openclaw gateway restart && sleep 5
```

> ⚠️ Do not quote the region value (`us-west-2` not `"us-west-2"`) — OpenClaw rejects it as an invalid hostname component.

---

### 5. Set Claude Sonnet as Default Model

```bash
openclaw config set agents.defaults.models '{"amazon-bedrock/us.anthropic.claude-sonnet-4-6": {}}' --replace
openclaw gateway restart
```

---

### 6. Install the Skill

```bash
mkdir -p ~/.openclaw/skills/zurich-damage-report
cp SKILL.md ~/.openclaw/skills/zurich-damage-report/SKILL.md
openclaw skills install ~/.openclaw/skills/zurich-damage-report
openclaw gateway restart
```

Verify:

```bash
openclaw skills list | grep zurich
```

---

### 7. Chat

```bash
openclaw dashboard
```

Type `/damage_report` and start chatting.

---

## Refreshing AWS Credentials

Event/temporary credentials expire. When you see `UnrecognizedClientException`, refresh:

```bash
# Paste new export lines in terminal first, then:
openclaw gateway stop && \
sed -i '' '/^export AWS/d' ~/.openclaw/service-env/ai.openclaw.gateway.env && \
printf 'export AWS_ACCESS_KEY_ID="%s"\nexport AWS_SECRET_ACCESS_KEY="%s"\nexport AWS_SESSION_TOKEN="%s"\nexport AWS_REGION=us-west-2\nexport AWS_DEFAULT_REGION=us-west-2\n' \
  "$AWS_ACCESS_KEY_ID" "$AWS_SECRET_ACCESS_KEY" "$AWS_SESSION_TOKEN" \
  >> ~/.openclaw/service-env/ai.openclaw.gateway.env && \
openclaw gateway restart
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `gateway token missing` | Run `openclaw configure` |
| `plugin not installed: amazon-bedrock` | Run `openclaw plugins install @openclaw/amazon-bedrock-provider` |
| `Could not load credentials` | Re-inject AWS credentials into the env file |
| `region="" is not a valid hostname component` | Use `AWS_REGION=us-west-2` without quotes |
| `UnrecognizedClientException` | Credentials expired — get fresh ones |
| `Invocation of model ID ... isn't supported` | Use `us.anthropic.claude-sonnet-4-6` (with `us.` prefix) |
| Bedrock not in `models list` | Run `openclaw models list --all` |

---

## Why OpenClaw + Bedrock?

- **Any channel** — OpenClaw connects to WhatsApp, Telegram, iMessage, Slack and more. Citizens report damage from wherever they already are.
- **Multilingual** — Claude understands German, English, Italian, French out of the box. No extra configuration.
- **Structured output** — the AI extracts and validates all required fields before submitting. No incomplete reports.
- **Private** — OpenClaw runs on your own hardware. No data sent to third-party chat platforms.
- **Extensible** — the same skill pattern works for any form: noise complaints, permit requests, emergency reports.

---

## Built With

- [OpenClaw](https://openclaw.ai) — self-hosted AI gateway
- [Amazon Bedrock](https://aws.amazon.com/bedrock/) — Claude Sonnet 4.6
- [Amazon DynamoDB](https://aws.amazon.com/dynamodb/) — damage report storage
- [Amazon API Gateway](https://aws.amazon.com/api-gateway/) — secure REST endpoint
