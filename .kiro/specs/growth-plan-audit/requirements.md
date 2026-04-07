# Requirements Document

## Introduction

This specification defines the requirements for a read-only audit of the ai1stseo.com codebase against a 5-month growth plan. The audit produces a structured gap report mapping existing systems, missing capabilities, risk areas, and a recommended build order — without modifying any code. The deliverable is a single markdown report (`docs/AI1STSEO_5_MONTH_IMPLEMENTATION_GAP_REPORT.md`) that serves as the technical blueprint before any implementation begins.

## Glossary

- **Audit_Engine**: The analysis process that inspects the codebase and produces the gap report
- **Gap_Report**: The markdown document output (`docs/AI1STSEO_5_MONTH_IMPLEMENTATION_GAP_REPORT.md`) containing all audit findings
- **Growth_Plan**: The 5-month phased plan covering email, social, content, community, and scaling systems
- **Existing_System**: A module, file, or feature already present in the repository
- **Missing_System**: A capability required by the Growth_Plan that has no implementation in the repository
- **Partial_System**: A capability that has some implementation but is incomplete or not wired for the Growth_Plan use case
- **External_Blocker**: A dependency on a third-party API credential, account, or service that prevents a feature from functioning
- **Isolated_Module**: A new file or directory that can be created without modifying shared core logic or teammates' work
- **Impact_Proposal**: A file-by-file listing of inspection targets, future change candidates, and new module recommendations
- **Phase**: One of the five monthly milestones in the Growth_Plan (Month 1 through Month 5)

## Requirements

### Requirement 1: Inspection Scope Definition

**User Story:** As a project lead, I want the audit to define its inspection scope before analysis begins, so that the team knows exactly which files and systems are being evaluated.

#### Acceptance Criteria

1. THE Audit_Engine SHALL produce a list of all repository files inspected during the audit, grouped by functional area (email, social, content, analytics, integrations)
2. THE Audit_Engine SHALL identify and exclude files belonging to teammates' test directories (dev4-*, postiz-setup) from modification scope while still cataloging their existence
3. THE Audit_Engine SHALL map each inspected file to one or more Growth_Plan phases (Month 1 through Month 5)
4. WHEN a file serves multiple Growth_Plan phases, THE Audit_Engine SHALL list all applicable phases for that file

### Requirement 2: Existing Systems Inventory

**User Story:** As a developer, I want a complete inventory of what already exists in the repo related to the growth plan, so that I know what I can build on.

#### Acceptance Criteria

1. THE Audit_Engine SHALL catalog all existing social media publishing modules (buffer_publisher.py, postiz_publisher.py, reddit_publisher.py, import_social_posts.py) with their current integration status (configured, stub, or non-functional)
2. THE Audit_Engine SHALL catalog all existing content generation modules (content_generator.py, ai_chatbot.py, ai_ranking_service.py, aeo_optimizer.py) with their current capabilities
3. THE Audit_Engine SHALL catalog all existing AI provider integrations (ai_provider.py, llm_service.py, bedrock_helper.py) with their supported models and fallback chains
4. THE Audit_Engine SHALL catalog all existing database schemas (geo_probes, ai_visibility_history, content_briefs, social_posts, answer_fingerprints, model_comparisons, share_of_voice, prompt_simulations) with their column definitions
5. THE Audit_Engine SHALL catalog all existing API endpoints from app.py grouped by functional domain (auth, SEO analysis, GEO monitoring, AEO, content, social, chatbot, LLM)
6. THE Audit_Engine SHALL catalog the existing Month 1 research framework (month1_api.py, month1_research/ directory) with its 8 deliverables and async job infrastructure
7. THE Audit_Engine SHALL classify each existing system as "fully operational", "partially operational", or "stub/placeholder" based on whether it requires external credentials to function

### Requirement 3: Missing Systems Identification by Phase

**User Story:** As a project lead, I want to know what is missing from the repo for each month of the growth plan, so that I can prioritize implementation work.

#### Acceptance Criteria

1. WHEN analyzing Month 1 (Foundation and Automation Setup), THE Audit_Engine SHALL identify gaps in email signup and newsletter capture, lead magnet delivery, email provider integration, and foundational analytics and event tracking
2. WHEN analyzing Month 2 (Content Engine and Audience Seeding), THE Audit_Engine SHALL identify gaps in content repurposing pipelines, social scheduling automation across all target platforms (X, LinkedIn, Instagram, Facebook, TikTok, YouTube, Reddit), and UTM tracking for campaign attribution
3. WHEN analyzing Month 3 (Community and UGC Activation), THE Audit_Engine SHALL identify gaps in UGC collection workflows, referral systems, challenge and contest mechanics, and community engagement tracking
4. WHEN analyzing Month 4 (Authority and Viral Amplification), THE Audit_Engine SHALL identify gaps in influencer outreach tooling, viral content amplification, cross-platform syndication automation, and authority signal measurement
5. WHEN analyzing Month 5 (Scale, Optimize and Hit 100K), THE Audit_Engine SHALL identify gaps in KPI dashboard and reporting, A/B testing infrastructure, performance optimization tooling, and scaling automation
6. FOR EACH missing system, THE Audit_Engine SHALL classify the gap as "completely missing", "partially exists", or "blocked by external dependency"

### Requirement 4: External Blockers and Manual Dependencies

**User Story:** As a developer, I want to know which features are blocked by external accounts, API keys, or manual setup steps, so that I can plan credential acquisition in parallel with development.

#### Acceptance Criteria

1. THE Audit_Engine SHALL list all environment variables referenced in the codebase that relate to Growth_Plan features (POSTIZ_API_KEY, BUFFER_API_KEY, REDDIT_CLIENT_ID, GROQ_API_KEY, and similar)
2. FOR EACH external blocker, THE Audit_Engine SHALL document the service name, the signup URL, the estimated cost (free tier or paid), and the manual steps required to obtain credentials
3. THE Audit_Engine SHALL identify which Growth_Plan features can proceed with placeholder credentials and graceful failure versus which features are completely blocked without live credentials
4. WHEN a feature requires a third-party account that has not been created, THE Audit_Engine SHALL flag the account creation as a manual dependency with an estimated time to complete

### Requirement 5: Risk Areas and Conflict-Prone Files

**User Story:** As a team lead, I want to know which files and modules are shared across teammates or have high modification risk, so that I can avoid merge conflicts and broken functionality.

#### Acceptance Criteria

1. THE Audit_Engine SHALL identify all shared files that multiple developers or features depend on (app.py, db.py, requirements.txt, index.html)
2. FOR EACH shared file, THE Audit_Engine SHALL describe the risk of modification (high, medium, low) and the reason for the risk rating
3. THE Audit_Engine SHALL identify files in teammates' directories (dev4-*, postiz-setup) that overlap with Growth_Plan functionality and recommend whether to reuse, wrap, or replace them
4. THE Audit_Engine SHALL flag any database schema changes that would be required for Growth_Plan features and assess their backward compatibility risk

### Requirement 6: File-by-File Impact Proposal

**User Story:** As a developer, I want a concrete file-level plan showing what to inspect, what might change later, and what new files to create, so that I can work safely in isolated modules.

#### Acceptance Criteria

1. THE Gap_Report SHALL contain a table of files to inspect, listing the file path, its current purpose, and its relevance to the Growth_Plan
2. THE Gap_Report SHALL contain a table of files that would likely need future changes, listing the file path, the nature of the change, the affected Growth_Plan phase, and the risk level
3. THE Gap_Report SHALL contain a table of new files and modules to create, listing the proposed file path, its purpose, the Growth_Plan phase it serves, and confirmation that it does not modify shared core logic
4. THE Gap_Report SHALL confirm that all proposed new modules follow the isolation principle: new files and directories rather than modifications to shared logic

### Requirement 7: Recommended Build Order

**User Story:** As a project lead, I want a prioritized build order for implementing Growth_Plan features, so that the team can work efficiently without blocking each other.

#### Acceptance Criteria

1. THE Gap_Report SHALL contain a recommended build order that sequences implementation tasks across all five Growth_Plan phases
2. FOR EACH recommended task, THE Gap_Report SHALL specify the estimated effort (small, medium, large), the dependencies on other tasks, and whether it can be built as an Isolated_Module
3. THE Gap_Report SHALL identify the first three implementation tasks to execute after the audit is approved, with specific file paths and acceptance criteria for each
4. WHEN two tasks have no dependency relationship, THE Gap_Report SHALL indicate they can be executed in parallel

### Requirement 8: Report Structure and Output

**User Story:** As a stakeholder, I want the audit report saved in a specific location with a defined structure, so that the team can review and approve it before implementation begins.

#### Acceptance Criteria

1. THE Audit_Engine SHALL save the Gap_Report as `docs/AI1STSEO_5_MONTH_IMPLEMENTATION_GAP_REPORT.md`
2. THE Gap_Report SHALL contain an executive summary of no more than 500 words covering the overall readiness assessment
3. THE Gap_Report SHALL contain all sections: executive summary, existing systems inventory, missing systems by month, risk areas, file-by-file impact proposal, recommended build order, external blockers, and suggested first three implementation tasks
4. THE Gap_Report SHALL use markdown tables for structured data (file listings, environment variables, build order)
5. THE Gap_Report SHALL include a confirmation statement that no code changes were made during the audit

### Requirement 9: No-Code-Change Guarantee

**User Story:** As a team lead, I want a guarantee that the audit process does not modify any existing code, so that the production system remains stable.

#### Acceptance Criteria

1. THE Audit_Engine SHALL perform read-only operations on all existing repository files
2. THE Audit_Engine SHALL create only the Gap_Report file and its parent directory (docs/) as new filesystem artifacts
3. IF the Audit_Engine encounters a file it cannot read, THEN THE Audit_Engine SHALL log the file path in the Gap_Report and continue without modification
4. THE Gap_Report SHALL include a final section confirming zero code modifications were made, listing only the files created by the audit process
