# Feature Specification: Knowledge Assistant Design for Every Role

**Feature Branch**: `006-knowledge-assistant-design`

**Created**: 2026-10-08

**Status**: Draft

**Input**: User description: "Follow this design (the Knowledge Assistant screen: title with a 'Secure retrieval active' badge, tabs AI Assistant, Knowledge Base, Text Assistant, History, and a History card with a search box, 'Both assistants' and 'All outcomes' dropdowns, rows with an outcome chip, Open and Ask again) for all roles: client, admin and advocate. Use the same keys to develop the complete process."

## Clarifications

- Q: The reference uses its own blue and white look. Does the screen copy that look exactly? → A: It copies the layout, wording and controls exactly, but uses MrCourt's navy, ivory and gold colours and fonts, because the project's constitution requires the shared design tokens. Buttons are navy (gold in dark mode) instead of blue.
- Q: Administrators had no Ask screen. What do they get? → A: The same Knowledge Assistant page. They can ask cited questions against the shared knowledge, manage shared sources, use the Text Assistant (and add conversations as shared sources), and see History. Their History can also show **everyone's questions in the workspace**, as the reference screen says; showing it is recorded in the audit log, and only the list is shown (no answers).
- Q: Keys? → A: The existing keys in `backend/.env` power the same features for every role; nothing new is needed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One Knowledge Assistant page, the same layout for everyone (Priority: P1)

Advocates, clients and administrators open the same page: the title "Knowledge Assistant", a short description, a green "Secure retrieval active" badge, and four icon tabs (AI Assistant, Knowledge Base, Text Assistant, History). What each tab offers depends on the role, but the layout, wording and controls are identical.

**Independent Test**: Sign in as each role, open the page, and confirm the title, badge and four tabs; confirm role-specific controls (clients cannot add sources; administrators manage shared sources).

**Acceptance Scenarios**:

1. **Given** any signed-in role, **When** they open the page, **Then** they see "Knowledge Assistant", the secure-retrieval badge, and the tabs AI Assistant, Knowledge Base, Text Assistant and History with icons.
2. **Given** an administrator, **Then** the page is in their menu, they can ask cited questions from shared sources, and the assistant (agent) mode stays off for them.
3. **Given** a client, **Then** they can ask, read the shared sources, keep Text Assistant conversations and see their own History, but cannot add sources.
4. **Given** the page, **Then** all controls are keyboard operable, labelled, and work in light and dark themes and on a phone.

### User Story 2 - History looks and works like the reference (Priority: P1)

The History tab is one card with a search box and two dropdowns ("Both assistants / AI Assistant / Text Assistant" and "All outcomes / Answered / No information found"), a line explaining that every question is kept even after a conversation is deleted, and rows showing the question, date, which assistant and Typed or Voice, an outcome chip, **Open** and **Ask again**.

**Acceptance Scenarios**:

1. **Given** past questions, **Then** each row shows the question, "date · AI Assistant or Text Assistant · Typed or Voice", an outcome chip ("Answered", "No information found", or "Saved" for conversations), an outlined Open button and a solid Ask again button.
2. **Given** the dropdowns and search, **Then** they filter the list together; an empty result says "No questions match."
3. **Given** a Text Assistant entry, **Then** Open shows its lines and Ask again is not offered.

### User Story 3 - Administrators can review the workspace's questions, on the record (Priority: P2)

On the History tab an administrator can switch from "My questions" to "Everyone's questions". The list shows who asked, when, which assistant, Typed or Voice, and the outcome; it does not show answers or conversation text, and Open and Ask again are not offered for other people's entries. Showing it is recorded in the audit log (without the question text).

**Acceptance Scenarios**:

1. **Given** an administrator, **When** they choose Everyone's questions, **Then** they see the workspace's questions with the asker's name, and an audit entry "Opened a person's question history" is written with no question text.
2. **Given** an advocate or client, **Then** they cannot see that option or call its data.
3. **Given** search and the two dropdowns, **Then** they apply to the workspace list too.

## Requirements *(mandatory)*

- **FR-001**: The page MUST be titled "Knowledge Assistant", show a "Secure retrieval active" badge, and use the tab names AI Assistant, Knowledge Base, Text Assistant and History with icons, for every role.
- **FR-002**: Administrators MUST be able to use the AI Assistant tab (cited answers from shared sources), the Knowledge Base tab (add and remove shared sources), the Text Assistant tab (including adding a conversation as a shared source) and their own History.
- **FR-003**: The agent mode MUST stay unavailable to administrators; clients and advocates keep their current abilities and limits.
- **FR-004**: History MUST present a search box, an assistant dropdown, an outcome dropdown and a Typed or voice dropdown, with rows as described above.
- **FR-005**: Administrators MUST be able to list everyone's questions, with the asker's name, and each such listing MUST write an audit entry without question text. Answers and conversation text of other people MUST NOT be shown to administrators.
- **FR-006**: The design tokens (colours, fonts) of the project MUST be used; no hard-coded colours.
- **FR-007**: All new and changed controls MUST meet the project's accessibility rules in both themes at desktop and phone widths.

## Success Criteria

- **SC-001**: In browser tests each role sees the same title, badge and four tabs, and the role-specific differences hold.
- **SC-002**: An administrator's workspace listing writes exactly one audit entry per listing, never containing question text, and no non-administrator can reach it.
- **SC-003**: All screens pass the automated accessibility checks in both themes at desktop and phone widths.

## Assumptions

- The navigation entry keeps the prototype's wording "Ask MrCourt" for advocates and clients so the pixel-checked navigation stays identical; the page title inside is "Knowledge Assistant". Administrators get the same entry in their own menu.
- Answers for administrators use shared sources only (administrators have no private notes).
- Everything else (meaning-based search, OCR, speech) already works through the same keys and applies to every role.
