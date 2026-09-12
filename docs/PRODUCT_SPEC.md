# MASTER PROMPT — BUILD TUTOROS

You are the lead software architect, senior full-stack engineer, AI engineer, database architect, UI/UX engineer, and QA engineer responsible for building a production-quality application called **TutorOS**.

Do not treat this as a basic college CRUD project.

The goal is to build a polished, scalable, portfolio-grade EdTech SaaS product that could realistically be used by independent tuition teachers and small coaching institutes.

---

# 1. PRODUCT VISION

## Product Name

**TutorOS**

## Tagline

**AI-powered academic operating system for tutors.**

## Core idea

TutorOS is a full-stack academic management and personalized learning platform for local tuition teachers and small coaching institutes.

It brings together:

* student management
* batch/class management
* subjects and topics
* homework
* document/PDF management
* online assessments
* student submissions
* grading
* attendance
* performance analytics
* topic-level mastery
* AI question generation
* AI PDF-to-assessment conversion
* personalized practice
* AI-generated teaching insights

The core learning loop is:

**Teach → Assign → Assess → Analyze → Identify gaps → Personalize → Improve**

The application should make this loop seamless.

---

# 2. THE PROBLEM

Local tutors commonly use fragmented tools:

* WhatsApp for homework
* notebooks for marks
* Excel/Google Sheets for performance
* Google Forms for quizzes
* PDFs for tests
* manual evaluation
* manual identification of weak topics

TutorOS should consolidate this workflow into one system.

The most important problem we solve is not simply:

> "How can a teacher manage students?"

The more valuable problem is:

> "How can assessment data help a teacher understand exactly where every student is struggling and decide what to teach or assign next?"

Therefore, **student performance intelligence is the heart of the application.**

---

# 3. PRIMARY USER TYPES

Implement role-based access.

## Teacher

Teachers can:

* create/manage batches
* add students
* manage subjects
* manage chapters/topics
* create homework
* upload homework PDFs
* create tests
* upload existing question papers
* convert PDFs into structured assessments
* review AI-extracted questions
* publish assessments
* monitor submissions
* grade submissions
* view student analytics
* view class analytics
* track attendance
* receive AI teaching insights

## Student

Students can:

* view enrolled batches
* view homework
* download files
* upload homework
* view upcoming tests
* take online tests
* submit tests
* view results
* view performance
* view topic mastery
* receive personalized practice recommendations
* complete practice sets

## Parent

Do NOT prioritize parent functionality in the initial MVP.

Design the architecture so a parent role can be added later.

---

# 4. PRODUCT PRINCIPLES

Follow these principles throughout development:

### 1. Production quality over feature count

Do not build dozens of shallow features.

Build fewer features properly.

### 2. AI must assist, not blindly control

AI-generated content must go through teacher review before being published.

Never automatically publish AI-generated assessments.

### 3. Analytics must be explainable

Do not simply output an unexplained "AI score."

Store the underlying metrics and make the calculation understandable.

### 4. Strong separation of concerns

Separate:

* frontend
* backend
* database
* AI services
* document processing
* analytics
* background jobs

### 5. Security first

Implement:

* authentication
* authorization
* input validation
* secure password storage
* secure file handling
* resource-level access control
* rate limiting where appropriate

### 6. Build for extensibility

The MVP should not require a rewrite to support future features.

---

# 5. RECOMMENDED TECH STACK

Use this stack unless the existing repository makes it technically unreasonable.

## Frontend

* Next.js
* TypeScript
* React
* Tailwind CSS
* shadcn/ui or another high-quality component system
* React Hook Form
* Zod
* TanStack Query where appropriate
* Recharts for analytics

## Backend

* Python
* FastAPI
* Pydantic
* SQLAlchemy
* Alembic

## Database

* PostgreSQL

## Authentication

Use secure session/JWT architecture appropriate for the stack.

Passwords must be hashed using a modern password hashing algorithm.

## File storage

Use S3-compatible object storage abstraction.

Do not tightly couple application logic to one storage provider.

## Background processing

Use Redis + Celery/RQ or an equivalent architecture for:

* PDF processing
* OCR
* AI generation
* analytics recalculation
* notifications
* other long-running tasks

## AI

Create a provider abstraction.

Do not hard-code the entire application to one AI provider.

The AI service should support structured JSON output.

## Testing

Use:

* Pytest for backend
* appropriate frontend testing
* API integration tests
* end-to-end tests for critical workflows

## Deployment

Structure the application so it can be deployed using:

* frontend hosting
* backend hosting
* managed PostgreSQL
* object storage
* Redis

Do not hard-code deployment-specific assumptions.

---

# 6. HIGH-LEVEL ARCHITECTURE

Use a modular architecture.

Conceptually:

```
                TutorOS
                   |
        +----------+----------+
        |                     |
     Frontend               Backend
   Next.js/React            FastAPI
        |                     |
        |        +------------+------------+
        |        |            |            |
        |       Auth       Academic       AI
        |                    Engine      Engine
        |        |            |            |
        +--------+------------+------------+
                     |
                PostgreSQL
                     |
             +-------+-------+
             |               |
         File Storage      Redis
                             |
                     Background Workers
```

AI/document pipeline:

PDF
↓
Upload
↓
Storage
↓
Background job
↓
Text extraction / OCR
↓
Question segmentation
↓
Topic classification
↓
Difficulty classification
↓
Structured question JSON
↓
Validation
↓
Teacher review
↓
Publish

Performance pipeline:

Assessment
↓
Questions
↓
Student responses
↓
Marks
↓
Topic aggregation
↓
Mastery calculation
↓
Trend detection
↓
Weak-topic detection
↓
Recommendation engine
↓
AI explanation / personalized practice

---

# 7. DATABASE DESIGN

Create a properly normalized PostgreSQL schema.

At minimum consider these entities:

## users

Fields:

* id
* name
* email
* password_hash
* role
* created_at
* updated_at

Roles:

* TEACHER
* STUDENT
* PARENT
* ADMIN

## teacher_profiles

* id
* user_id
* institute_name
* bio
* created_at

## student_profiles

* id
* user_id
* grade
* academic_year
* created_at

## batches

* id
* teacher_id
* name
* grade
* section
* academic_year
* created_at

## batch_students

Many-to-many relationship:

* batch_id
* student_id
* joined_at
* status

## subjects

* id
* name
* grade

## topics

* id
* subject_id
* chapter
* name
* description

## homework

* id
* teacher_id
* batch_id
* subject_id
* topic_id
* title
* description
* due_date
* status
* created_at

## homework_attachments

* id
* homework_id
* file_name
* storage_key
* mime_type
* file_size

## homework_submissions

* id
* homework_id
* student_id
* submitted_at
* status
* score
* feedback

## assessments

* id
* teacher_id
* batch_id
* subject_id
* title
* description
* duration_minutes
* total_marks
* status
* scheduled_at
* created_at

Statuses:

* DRAFT
* REVIEW
* PUBLISHED
* CLOSED

## questions

* id
* assessment_id
* question_text
* question_type
* topic_id
* difficulty
* marks
* order_index
* explanation
* source
* created_at

Question types should support:

* MCQ
* MULTI_SELECT
* TRUE_FALSE
* NUMERICAL
* SHORT_ANSWER
* LONG_ANSWER

## question_options

* id
* question_id
* option_text
* is_correct

## assessment_attempts

* id
* assessment_id
* student_id
* started_at
* submitted_at
* status
* total_score

## responses

* id
* attempt_id
* question_id
* response_text
* selected_option
* score
* is_correct
* time_spent_seconds

## attendance

* id
* batch_id
* student_id
* date
* status

## performance_snapshots

Store calculated performance metrics.

Possible fields:

* student_id
* topic_id
* mastery_score
* accuracy
* recent_accuracy
* consistency_score
* questions_attempted
* updated_at

## recommendations

* id
* student_id
* topic_id
* type
* recommendation_text
* priority
* generated_at
* status

## practice_sets

* id
* student_id
* topic_id
* title
* difficulty
* created_at

## practice_questions

* id
* practice_set_id
* question_text
* question_type
* difficulty
* marks

Design indexes and foreign keys properly.

Use UUIDs where appropriate.

---

# 8. AUTHENTICATION AND AUTHORIZATION

Implement proper authentication.

Requirements:

* registration
* login
* logout
* password hashing
* authenticated sessions
* protected routes
* role-based authorization

More importantly, implement **resource-level authorization**.

Examples:

A student must NOT be able to:

* access another student's submissions
* access another student's analytics
* access teacher dashboards

Teacher A must NOT be able to:

* access Teacher B's batches
* access Teacher B's students
* access Teacher B's assessments

Never rely only on frontend checks.

All authorization must also be enforced on the backend.

---

# 9. TEACHER DASHBOARD

Create a polished SaaS-style dashboard.

The dashboard should show:

### Overview

* total students
* total batches
* pending homework
* upcoming tests
* recent submissions

### Student attention panel

Example:

Student | Topic | Mastery | Trend

Rahul | Trigonometry | 47% | ↓
Ananya | Geometry | 54% | →
Aryan | Algebra | 61% | ↑

### Class performance

Show:

* average score
* attendance
* topic mastery
* improvement

### AI teaching insight

Example:

"Trigonometry is currently the weakest topic in Class 10-A. 14 of 27 students scored below 60% across the last two assessments."

Only generate this after calculating the underlying statistics.

---

# 10. STUDENT DASHBOARD

Keep it simpler.

Show:

* overall mastery
* recent tests
* upcoming homework
* upcoming tests
* strengths
* weak topics
* recommendations

Example:

Overall mastery: 74%

Strengths:

* Algebra 88%
* Statistics 83%

Needs practice:

* Trigonometry 48%
* Geometry 63%

Recommended:

"10-question Trigonometry practice set"

---

# 11. HOMEWORK SYSTEM

Teachers should be able to:

* create homework manually
* upload PDFs
* attach multiple files
* assign to batches
* specify due dates
* add instructions

Students should be able to:

* see assignments
* download attachments
* upload submissions
* replace submissions before deadline
* see submission status

Teacher dashboard should show:

Submitted
Pending
Late

Use clear visual indicators.

---

# 12. ONLINE ASSESSMENT ENGINE

Build a robust online testing system.

Features:

* test instructions
* countdown timer
* question navigation
* previous/next
* mark for review
* autosave
* automatic submission
* answer persistence
* attempt status

Support:

* MCQ
* multi-select
* true/false
* numerical
* short answer
* long answer

Automatically grade objective questions.

For subjective questions, allow teacher grading.

Never trust marks supplied by the frontend.

Calculate scores on the backend.

---

# 13. SIGNATURE FEATURE — PDF TO ASSESSMENT

Build a proper document-processing pipeline.

Teacher uploads PDF.

Backend:

1. validates file
2. stores file
3. creates processing job
4. extracts text
5. uses OCR when required
6. detects questions
7. extracts options
8. detects answer key where possible
9. identifies topic
10. estimates difficulty
11. creates structured question objects
12. validates schema
13. saves draft assessment

The teacher then sees:

### AI Extraction Review

Question 1

Text:
...

Topic:
Trigonometry

Difficulty:
Medium

Marks:
2

Source:
AI extracted

Actions:

* Edit
* Delete
* Regenerate
* Change topic
* Change difficulty
* Change marks

Only after teacher approval:

**Publish Assessment**

Build this using a background job architecture so large documents don't block the HTTP request.

---

# 14. AI QUESTION GENERATOR

Create a teacher workflow:

Create Assessment
↓
Generate with AI

Inputs:

* grade
* subject
* topic
* number of questions
* difficulty
* question types
* total marks
* duration

AI must return strict structured JSON.

Validate output with Pydantic/Zod.

Perform basic checks:

* missing fields
* duplicate questions
* invalid marks
* invalid question type
* malformed options
* missing correct answers

Teacher must review before publishing.

---

# 15. TOPIC CLASSIFICATION

Every assessment question should ideally have:

* subject
* chapter
* topic
* difficulty
* question type
* learning objective

For AI-generated or extracted questions, allow the teacher to override AI classifications.

Never make AI classifications immutable.

---

# 16. PERFORMANCE ENGINE

This is one of the most important components.

Do not calculate student performance only from overall marks.

Calculate:

### Accuracy

correct answers / attempted questions

### Topic accuracy

marks obtained for topic / maximum marks for topic

### Recent performance

Give more weight to recent assessments.

### Consistency

Measure variation in performance.

### Difficulty-adjusted performance

A hard question can carry different weight than an easy question.

---

# 17. MASTERY SCORE

Create a transparent mastery algorithm.

Start with something like:

Mastery Score =

40% recent performance
+
30% historical performance
+
20% difficulty-adjusted performance
+
10% consistency

Keep this configurable.

Normalize to 0–100.

Categories:

0–40:
Critical

40–60:
Needs Improvement

60–75:
Developing

75–90:
Strong

90–100:
Mastered

Do not pretend this is scientifically perfect.

Clearly label it as a product-defined mastery model.

Document the methodology.

---

# 18. TREND DETECTION

Detect:

* improving
* declining
* stable
* insufficient data

Example:

Trigonometry:

41%
46%
52%
61%

Trend:

Improving ↑

Do not use arbitrary trends without documenting the calculation.

---

# 19. PERSONALIZED PRACTICE

If a student has a weak topic:

Example:

Trigonometry = 48%

Generate:

Personalized Practice Set

* 5 easy questions
* 3 medium questions
* 2 hard questions

The questions should target the weak topic.

After completion:

Recalculate performance.

Show:

Before:
48%

After:
57%

Improvement:
+9 percentage points

Make it clear that correlation does not automatically prove causation.

---

# 20. AI PERFORMANCE INSIGHTS

Do not send raw database data blindly to an LLM.

Instead:

Database
↓
Analytics engine
↓
Structured student profile
↓
AI
↓
Natural language insight

Example input:

{
"student": "Rahul",
"topic": "Trigonometry",
"mastery": 48,
"recent_accuracy": 52,
"historical_accuracy": 45,
"trend": "improving",
"questions_attempted": 37
}

AI generates:

"Rahul is currently below the target mastery level in Trigonometry, but his recent performance is improving. Additional practice on trigonometric identities may help reinforce the concept."

Do not let the AI invent statistics.

---

# 21. CLASS ANALYTICS

Teacher should be able to select:

Batch → Subject → Topic

and see:

* class average
* median
* highest
* lowest
* distribution
* topic mastery
* student performance
* improvement trends

Question-level analytics:

* percentage correct
* average time
* difficulty
* question performance

---

# 22. ATTENDANCE ANALYTICS

Implement attendance tracking.

Teacher can mark:

Present
Absent
Late

Then calculate:

* attendance percentage
* attendance trend

Optionally show:

Attendance vs performance correlation.

Be careful not to claim causation.

Use language like:

"Students with higher attendance in this batch also show higher average assessment scores."

---

# 23. UI/UX REQUIREMENTS

The application should feel like a modern SaaS product.

Do NOT make it look like a generic college project.

Design principles:

* clean
* minimal
* professional
* responsive
* accessible
* consistent spacing
* strong typography
* intuitive navigation
* useful empty states
* loading states
* error states
* confirmation states

Teacher dashboard should feel data-rich.

Student dashboard should feel simple.

Use cards, tables, charts and contextual actions appropriately.

Avoid excessive animations.

---

# 24. NAVIGATION

Teacher:

Dashboard
Students
Batches
Subjects
Homework
Assessments
Analytics
Attendance
AI Tools
Settings

Student:

Dashboard
Homework
Tests
Practice
Progress
Profile

---

# 25. API DESIGN

Create clean REST APIs.

Examples:

POST /auth/register
POST /auth/login
POST /auth/logout

GET /teachers/dashboard

GET /batches
POST /batches
GET /batches/{id}
PATCH /batches/{id}

GET /students
GET /students/{id}

POST /homework
GET /homework
GET /homework/{id}
POST /homework/{id}/submissions

POST /assessments
GET /assessments
GET /assessments/{id}
POST /assessments/{id}/publish

POST /assessments/{id}/attempts
POST /attempts/{id}/responses
POST /attempts/{id}/submit

GET /students/{id}/performance
GET /students/{id}/topics/{topic_id}/performance

POST /ai/generate-questions
POST /documents/process

Keep API naming consistent.

Use proper status codes.

Validate all inputs.

Return consistent error structures.

---

# 26. BACKEND ENGINEERING STANDARDS

Use:

* service layer
* repository/data access layer where useful
* Pydantic schemas
* dependency injection
* centralized error handling
* logging
* configuration management
* environment variables
* database migrations

Do not put business logic directly inside route handlers.

Example:

Router
↓
Service
↓
Repository
↓
Database

For AI:

Router
↓
AI Service
↓
Provider abstraction

For analytics:

Router
↓
Analytics Service
↓
Database

---

# 27. FRONTEND ENGINEERING STANDARDS

Use:

* reusable components
* typed API clients
* form validation
* loading states
* error handling
* optimistic updates only where safe
* reusable charts
* reusable tables
* reusable modal/dialog components

Do not duplicate components unnecessarily.

Keep business logic out of presentational components where possible.

---

# 28. SECURITY

Implement:

* password hashing
* secure authentication
* authorization
* CORS configuration
* input validation
* SQL injection protection through ORM/parameterization
* file validation
* file size limits
* MIME validation
* safe file names
* secure file access
* rate limiting for expensive endpoints
* protection against unauthorized resource access

Never expose internal storage keys unnecessarily.

Never put secrets in frontend code.

Use environment variables.

---

# 29. OBSERVABILITY

Add useful logging.

Log:

* authentication events
* assessment creation
* document processing failures
* AI failures
* background job failures
* important API errors

Do not log passwords, tokens or sensitive user data.

---

# 30. TESTING STRATEGY

Do not consider the project complete without tests.

At minimum test:

### Authentication

* registration
* login
* invalid credentials
* protected routes

### Authorization

* student cannot access another student
* teacher cannot access another teacher's batch

### Assessments

* creation
* publishing
* attempting
* autosaving
* submission
* scoring

### Homework

* creation
* submission
* deadline behavior

### Analytics

* correct topic aggregation
* mastery calculation
* trend calculation

### AI

Mock AI providers in tests.

Test malformed AI responses.

Test schema validation.

### PDF processing

Test extraction pipeline with sample documents.

---

# 31. MVP PRIORITY

Do NOT implement every feature immediately.

Build in this order.

## Phase 0 — Foundation

* repository inspection
* architecture
* project setup
* environment configuration
* database
* migrations
* authentication
* base UI

## Phase 1 — Core academic management

* teachers
* students
* batches
* subjects
* topics

## Phase 2 — Homework

* creation
* attachments
* submissions
* deadlines
* teacher review

## Phase 3 — Assessment engine

* question creation
* tests
* attempts
* timer
* autosave
* submission
* grading

## Phase 4 — Analytics

* student performance
* topic performance
* class analytics
* trends
* dashboards

## Phase 5 — AI

* question generation
* PDF extraction
* topic classification
* difficulty classification
* teacher review workflow

## Phase 6 — Personalization

* mastery model
* weak-topic detection
* personalized practice
* AI insights

## Phase 7 — Production hardening

* testing
* security
* error handling
* logging
* performance
* deployment
* documentation

---

# 32. IMPORTANT DEVELOPMENT RULE

Before writing code:

1. Inspect the existing repository.
2. Understand what already exists.
3. Do not overwrite working code unnecessarily.
4. Identify the current stack.
5. Create a clear implementation plan.
6. Create/modify files incrementally.
7. Run tests after meaningful changes.
8. Fix errors rather than ignoring them.
9. Keep the application runnable throughout development.

If the repository is empty, initialize the project using the architecture described above.

---

# 33. DEVELOPMENT WORKFLOW

Work like a senior engineer.

For each major feature:

1. Explain briefly what you are implementing.
2. Define database changes.
3. Implement backend.
4. Implement frontend.
5. Connect frontend/backend.
6. Add validation.
7. Add tests.
8. Run tests.
9. Fix failures.
10. Verify the feature manually where possible.
11. Update documentation.

Do not generate a giant amount of code without validating it.

---

# 34. DEMO-FIRST PRODUCT FLOW

The final product must support this end-to-end demo:

### Teacher

Create:

"Class 10-A Mathematics"

Add 10 students.

Create topics:

* Algebra
* Geometry
* Trigonometry
* Statistics

Upload:

`Class10_Maths_Test.pdf`

System processes it.

AI extracts 20 questions.

Teacher reviews them.

Teacher publishes test.

### Student

Student logs in.

Starts test.

Answers questions.

Submits test.

### System

Automatically grades objective questions.

Stores responses.

Associates responses with topics.

Updates performance.

### Teacher

Teacher opens Rahul's profile.

Sees:

Algebra — 81%
Geometry — 72%
Statistics — 83%
Trigonometry — 39%

System says:

"Trigonometry is Rahul's primary learning gap."

Teacher clicks:

**Generate Practice**

System generates a 10-question personalized practice set.

Student completes it.

Analytics update.

This entire workflow should work reliably.

---

# 35. DATA SEEDING

Create realistic demo data.

Seed:

* 2–3 teachers
* 3–5 batches
* 30–50 students
* multiple subjects
* multiple topics
* several assessments
* hundreds of responses
* attendance records
* homework submissions

The dashboards should look meaningful immediately after setup.

Do not use obviously fake names like:

Student1, Student2, Test1.

Use realistic demo data.

---

# 36. README REQUIREMENTS

Create a professional README containing:

* project overview
* problem statement
* product features
* architecture diagram
* technology stack
* database architecture
* AI pipeline
* analytics methodology
* local setup
* environment variables
* database migrations
* test instructions
* deployment instructions
* screenshots section
* future improvements

Also include:

### Engineering decisions

Explain why:

* PostgreSQL
* FastAPI
* Next.js
* background jobs
* AI provider abstraction
* topic-level analytics
* mastery model

were chosen.

---

# 37. DOCUMENTATION

Create `/docs`.

Include:

`architecture.md`

`database.md`

`api.md`

`ai-pipeline.md`

`analytics.md`

`security.md`

`development.md`

Document important design decisions.

---

# 38. QUALITY BAR

The finished application should satisfy this standard:

### It should NOT feel like:

"Student Management System — College Project"

### It SHOULD feel like:

"A small EdTech SaaS product with intelligent assessment analytics."

The difference must be visible in:

* UI
* architecture
* database design
* API design
* analytics
* AI integration
* security
* testing
* documentation

---

# 39. WHAT NOT TO DO

Do NOT:

* create fake AI features
* hard-code analytics
* hard-code dashboard numbers
* use mock data in production paths
* store passwords in plaintext
* trust frontend-calculated marks
* allow unrestricted file uploads
* let AI publish assessments automatically
* put secrets in source code
* create unnecessary microservices
* over-engineer the MVP
* build features without tests
* claim ML accuracy without evaluation

Prefer a well-designed modular monolith initially.

Do not introduce microservices unless there is a genuine reason.

---

# 40. START NOW

First, inspect the repository thoroughly.

Determine:

* current files
* current framework
* existing dependencies
* existing database
* existing UI
* existing backend
* existing configuration
* existing functionality

Then provide:

## A. Current repository assessment

## B. Recommended architecture

## C. Implementation roadmap

## D. Database/schema plan

## E. Immediate next steps

Then **start implementing Phase 0 immediately**.

Do not stop after giving me a plan.

After Phase 0 is complete and verified, continue to Phase 1.

Keep the implementation incremental and testable.

Whenever you encounter an ambiguity, choose the option that best supports:

**security + maintainability + scalability + simplicity + portfolio quality.**

The ultimate objective is to create a project that I can confidently showcase in software engineering, AI/ML, data, and full-stack placement interviews.

Build it as if you are preparing it for a real product launch, not merely completing an academic assignment.
