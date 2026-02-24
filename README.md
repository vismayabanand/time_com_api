# Time.com Latest Stories API

## What this does
Exposes a GET endpoint that returns the latest 6 stories from Time.com homepage.

Endpoint:
- `GET /getTimeStories`

## Constraints followed
- Uses a basic approach to process HTML (string + regex).
- Does not use external/internal HTML parsing libraries.

## Run
python3 app.py

## Server
- http://localhost:8000/getTimeStories

## Test
- curl http://localhost:8000/getTimeStories

