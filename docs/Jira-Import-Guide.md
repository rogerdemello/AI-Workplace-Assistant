# AI Workplace Assistant
## Jira Import Guide

Version: 1.0  
Date: March 27, 2026

## 1. File to Import
Use the CSV file:
- docs/Jira-Backlog-Import.csv

## 2. Recommended Jira Setup
- Project type: Company-managed Scrum
- Story point field enabled
- Epic issue type enabled
- Sprint field enabled (board configured)

## 3. CSV Import Steps
1. Open Jira Settings -> System -> External System Import -> CSV.
2. Upload docs/Jira-Backlog-Import.csv.
3. Map columns:
   - Issue Type -> Issue Type
   - Summary -> Summary
   - Description -> Description
   - Priority -> Priority
   - Labels -> Labels
   - Epic Name -> Epic Name
   - Epic Link -> Epic Link
   - Story Points -> Story Points
   - Sprint -> Sprint
   - Fix Version -> Fix Version
4. Import epics and stories in one pass.
5. Verify stories are linked to epics and have estimates.

## 4. Post-Import Checklist
- Confirm all 8 epics were created.
- Confirm all stories are linked via Epic Link.
- Confirm sprint names exist and items are placed correctly.
- Confirm Story Points mapped and visible on backlog.
- Set board filters for labels: backend, frontend, ai, devops, qa.

## 5. Optional Enhancements
- Add Components: Platform, AI, Integrations, Analytics.
- Add custom field for Acceptance Criteria.
- Add workflow validators for Definition of Done.
