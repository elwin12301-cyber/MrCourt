<!--
Sync Impact Report
Version change: (template, unversioned) → 1.0.0
Modified principles: none (initial adoption; all placeholders replaced)
Added sections: Core Principles I–VI, Product & Compliance Constraints,
  Development Workflow & Quality Gates, Governance
Removed sections: none
Templates requiring updates: none; plan/spec/tasks templates read this file at runtime
Follow-up TODOs: none. Ratification date set to the date of first adoption.
-->
# MrCourt Constitution

## Core Principles

### I. Grounded, Cited Answers Only
Every legal answer MUST cite its source: the Act, section or judgment (for example BNS, BNSS, BSA,
the Constitution of India, or the Negotiable Instruments Act). An answer without a verifiable
source MUST NOT be presented as fact. When no reliable source is found, the product MUST say so
plainly and suggest how to rephrase, never guess.
Rationale: users act on legal information; an uncited or invented answer causes real harm.

### II. Informational Guidance, Not Legal Advice
All AI-generated output MUST be labelled as informational and not legal advice. AI-generated drafts
(notices, applications, replies, affidavits) MUST be fully editable by the user and MUST carry a
visible "review before use" flag. The product MUST NOT file, send or export legal documents on a
user's behalf without an explicit human action.
Rationale: the advocate remains professionally responsible; the tool assists, it does not decide.

### III. Privacy by Design (DPDP Act)
Personal and case data MUST be handled in line with India's Digital Personal Data Protection Act,
2023. Features MUST collect only the data they need, state the purpose, and give users a way to
manage or delete their data. Credentials, tokens and client data MUST NOT appear in source control,
logs or analytics. Sample or prototype data MUST be clearly fictional.
Rationale: case files and client details are confidential by nature.

### IV. Accessible and Responsive by Default
Every screen MUST work by keyboard alone, show visible focus states, and use semantic markup and
ARIA roles where native elements are insufficient. Light and dark themes MUST both be supported
with sufficient contrast, layouts MUST work at mobile widths, and animation MUST respect
`prefers-reduced-motion`.
Rationale: advocates and petitioners use varied devices and abilities, often on the move.

### V. Design System Consistency
UI MUST use the shared design tokens (navy, ivory and gold palette; Playfair Display for headings,
Inter for body text) defined as CSS variables, not hard-coded values. New components MUST reuse
existing patterns (cards, chips, pills, split screens) before introducing new ones.
Rationale: a consistent, serious visual identity builds trust in a legal product.

### VI. Simplicity and Prototype-First
Start with the simplest design that proves the idea. New dependencies, services and abstractions
MUST be justified by a present need, not a speculative one. Prototype behaviour that is not yet
real (for example export) MUST say so to the user instead of appearing to work.
Rationale: complexity is costly to maintain and hides defects in a high-trust domain.

## Product & Compliance Constraints

- Audience: two roles, Advocate and Petitioner. Features MUST state which role they serve.
- Legal scope: Indian law, using current statutes (BNS, BNSS, BSA) in preference to the repealed
  codes they replaced, unless a historical question requires otherwise.
- Sources: the indexed legal corpus is the only basis for cited answers; its coverage limits MUST
  be reflected in "no reliable source found" responses.
- Language: English first. Any added language MUST preserve citations verbatim.
- Disclaimers are part of the product and MUST NOT be removed to save space.

## Development Workflow & Quality Gates

- Work follows Spec Kit order: constitution, specify, plan, tasks, implement.
- Every spec and plan MUST include a check against Principles I–VI; violations MUST be justified
  in the plan's complexity section or the work revised.
- Changes touching legal answers or drafts MUST include tests or reviewed examples for both the
  cited case and the "no reliable source" case.
- UI changes MUST be checked for keyboard use, both themes and a narrow viewport before merge.
- Changes MUST NOT introduce secrets or real personal data into the repository.

## Governance

This constitution supersedes other practices and conventions in this project. Amendments MUST be
documented with a rationale, update the Sync Impact Report, and bump the version as follows: MAJOR
for removing or redefining a principle in a backward-incompatible way, MINOR for adding a principle
or materially expanding guidance, PATCH for clarifications and wording fixes. Specs, plans and
reviews MUST verify compliance with this constitution, and unjustified complexity MUST be rejected.
Compliance is reviewed whenever a plan is written and before each release.

**Version**: 1.0.0 | **Ratified**: 2026-10-07 | **Last Amended**: 2026-10-07
