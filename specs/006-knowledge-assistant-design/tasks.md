# Tasks: Knowledge Assistant design for every role

- [X] T001 Backend: let administrators use their own History, the Text Assistant and speech; add `GET /admin/questions` (workspace list with the asker, audited without text) in `backend/src/mrcourt/api/{admin,history,text,speech}.py`, `services/history.py`, `schemas/history.py`
- [X] T002 Backend tests for the above (every role may use speech and the Text Assistant, administrator's own history, workspace list content, audit entry, non-administrators refused, others' answers not openable) in `backend/tests/contract/`
- [X] T003 Page shell: title "Knowledge Assistant", secure badge, icon tabs AI Assistant, Knowledge Base, Text Assistant, History, per-tab description, in `frontend/src/pages/Ask.tsx`
- [X] T004 History card: search, assistant, outcome and Typed or voice dropdowns, row layout with outcome chip, Open and Ask again, administrator "Whose questions" switch, in `frontend/src/pages/ask/HistoryTab.tsx` and `frontend/src/services/history.ts`
- [X] T005 Routes and menu: `/ask` for administrators (menu entry "Ask MrCourt"), `/admin/knowledge` redirects to `/ask/knowledge`, administrators may add a conversation as a shared source, in `frontend/src/App.tsx`, `components/AppShell.tsx`, `pages/ask/TextAssistantTab.tsx`
- [X] T006 Styles in project tokens only (`.ka-*`, `.secure`, `.btn.outline`) in `frontend/src/styles/app.css`
- [X] T007 End-to-end tests for each role and the History card (`frontend/tests/e2e/knowledge-assistant.spec.ts`) and updates to tests that named the old tabs, filters and admin menu
- [X] T008 Full regression twice in a row; write `specs/006-knowledge-assistant-design/results.md`
- [ ] T009 Review by a person: administrators listing everyone's questions, against the DPDP Act and policy (cannot be done by the build; leave open)
