import { getToken } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type UserRole = "TEACHER" | "STUDENT" | "PARENT" | "ADMIN";

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export class ApiError extends Error {
  status: number;
  /** Populated when the backend returns a structured {errors: [...]} message (e.g. publish validation). */
  details: string[] | null;
  constructor(status: number, message: string, details: string[] | null = null) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

function extractError(body: unknown): { message: string; details: string[] | null } {
  const raw = (body as { error?: { message?: unknown } })?.error?.message;
  if (raw && typeof raw === "object" && Array.isArray((raw as { errors?: unknown }).errors)) {
    const errors = (raw as { errors: string[] }).errors;
    return { message: errors.join("; "), details: errors };
  }
  return { message: typeof raw === "string" ? raw : "Request failed", details: null };
}

async function request<T>(path: string, options: RequestInit = {}, auth = false): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (auth) {
    const token = getToken();
    if (token) {
      (headers as Record<string, string>).Authorization = `Bearer ${token}`;
    }
  }

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const { message, details } = extractError(body);
    throw new ApiError(response.status, message, details);
  }

  return response.json() as Promise<T>;
}

async function requestForm<T>(path: string, method: string, formData: FormData): Promise<T> {
  const headers: HeadersInit = {};
  const token = getToken();
  if (token) (headers as Record<string, string>).Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_URL}${path}`, { method, headers, body: formData });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const { message, details } = extractError(body);
    throw new ApiError(response.status, message, details);
  }

  return response.json() as Promise<T>;
}

export function register(name: string, email: string, password: string, role: UserRole = "STUDENT") {
  return request<TokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ name, email, password, role }),
  });
}

export function login(email: string, password: string) {
  return request<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function me() {
  return request<User>("/auth/me", {}, true);
}

export interface DashboardOverview {
  total_batches: number;
  total_students: number;
}

export interface Batch {
  id: string;
  teacher_id: string;
  name: string;
  grade: string | null;
  section: string | null;
  academic_year: string | null;
  created_at: string;
  student_count: number;
}

export interface BatchStudentEntry {
  student_id: string;
  name: string;
  email: string;
  status: "ACTIVE" | "REMOVED";
  joined_at: string;
}

export interface Student {
  id: string;
  name: string;
  email: string;
  created_at: string;
  grade: string | null;
  academic_year: string | null;
}

export interface Subject {
  id: string;
  name: string;
  grade: string | null;
}

export interface Topic {
  id: string;
  subject_id: string;
  chapter: string | null;
  name: string;
  description: string | null;
}

export function getDashboard() {
  return request<DashboardOverview>("/teachers/dashboard", {}, true);
}

export function listBatches() {
  return request<Batch[]>("/batches", {}, true);
}

export function getBatch(id: string) {
  return request<Batch>(`/batches/${id}`, {}, true);
}

export function createBatch(data: { name: string; grade?: string; section?: string; academic_year?: string }) {
  return request<Batch>("/batches", { method: "POST", body: JSON.stringify(data) }, true);
}

export function listBatchStudents(batchId: string) {
  return request<BatchStudentEntry[]>(`/batches/${batchId}/students`, {}, true);
}

export function addStudentToBatch(batchId: string, data: { name: string; email: string }) {
  return request<BatchStudentEntry>(
    `/batches/${batchId}/students`,
    { method: "POST", body: JSON.stringify(data) },
    true,
  );
}

export function listStudents() {
  return request<Student[]>("/students", {}, true);
}

export function listSubjects() {
  return request<Subject[]>("/subjects", {}, true);
}

export function createSubject(data: { name: string; grade?: string }) {
  return request<Subject>("/subjects", { method: "POST", body: JSON.stringify(data) }, true);
}

export function listTopics(subjectId?: string) {
  const query = subjectId ? `?subject_id=${subjectId}` : "";
  return request<Topic[]>(`/topics${query}`, {}, true);
}

export function createTopic(data: { subject_id: string; name: string; chapter?: string; description?: string }) {
  return request<Topic>("/topics", { method: "POST", body: JSON.stringify(data) }, true);
}

export interface HomeworkAttachment {
  id: string;
  file_name: string;
  mime_type: string;
  file_size: number;
}

export interface Homework {
  id: string;
  teacher_id: string;
  batch_id: string;
  subject_id: string;
  topic_id: string | null;
  title: string;
  description: string | null;
  due_date: string;
  allow_late_submissions: boolean;
  created_at: string;
  attachments: HomeworkAttachment[];
}

export type SubmissionStatus = "SUBMITTED" | "LATE";

export interface Submission {
  id: string;
  homework_id: string;
  student_id: string;
  submitted_at: string;
  status: SubmissionStatus;
  file_name: string;
  mime_type: string;
  file_size: number;
  score: number | null;
  feedback: string | null;
}

export interface RosterEntry {
  student_id: string;
  name: string;
  email: string;
  status: SubmissionStatus | null;
  submitted_at: string | null;
}

export function listHomework() {
  return request<Homework[]>("/homework", {}, true);
}

export function getHomework(id: string) {
  return request<Homework>(`/homework/${id}`, {}, true);
}

export function createHomework(data: {
  batch_id: string;
  subject_id: string;
  topic_id?: string;
  title: string;
  description?: string;
  due_date: string;
  files: File[];
}) {
  const form = new FormData();
  form.set("batch_id", data.batch_id);
  form.set("subject_id", data.subject_id);
  if (data.topic_id) form.set("topic_id", data.topic_id);
  form.set("title", data.title);
  if (data.description) form.set("description", data.description);
  form.set("due_date", data.due_date);
  for (const file of data.files) form.append("files", file);
  return requestForm<Homework>("/homework", "POST", form);
}

export function updateHomework(id: string, data: { allow_late_submissions?: boolean }) {
  return request<Homework>(`/homework/${id}`, { method: "PATCH", body: JSON.stringify(data) }, true);
}

async function downloadFile(url: string, fileName: string): Promise<void> {
  const token = getToken();
  const response = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new ApiError(response.status, "Download failed");
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(objectUrl);
}

export function downloadAttachment(homeworkId: string, attachment: HomeworkAttachment) {
  return downloadFile(`${API_URL}/homework/${homeworkId}/attachments/${attachment.id}/file`, attachment.file_name);
}

export function downloadSubmission(homeworkId: string, studentId: string, fileName: string) {
  return downloadFile(`${API_URL}/homework/${homeworkId}/submissions/${studentId}/file`, fileName);
}

export function listSubmissionRoster(homeworkId: string) {
  return request<RosterEntry[]>(`/homework/${homeworkId}/submissions`, {}, true);
}

export function getMySubmission(homeworkId: string) {
  return request<Submission>(`/homework/${homeworkId}/submissions/me`, {}, true);
}

export function submitHomework(homeworkId: string, file: File) {
  const form = new FormData();
  form.set("file", file);
  return requestForm<Submission>(`/homework/${homeworkId}/submissions`, "POST", form);
}

// ---------------------------------------------------------------------------
// Assessments
// ---------------------------------------------------------------------------

export type QuestionType = "MCQ" | "MULTI_SELECT" | "TRUE_FALSE" | "NUMERICAL" | "SHORT_ANSWER" | "LONG_ANSWER";
export type AssessmentStatus = "DRAFT" | "REVIEW" | "PUBLISHED" | "CLOSED";
export type AttemptStatus = "IN_PROGRESS" | "SUBMITTED" | "EXPIRED";

export interface Assessment {
  id: string;
  teacher_id: string;
  batch_id: string;
  subject_id: string;
  title: string;
  description: string | null;
  duration_minutes: number;
  total_marks: number;
  status: AssessmentStatus;
  created_at: string;
}

export interface QuestionOption {
  id: string;
  option_text: string;
  order_index: number;
  is_correct: boolean | null;
}

export interface Question {
  id: string;
  assessment_id: string;
  question_text: string;
  question_type: QuestionType;
  topic_id: string | null;
  difficulty: string | null;
  marks: number;
  order_index: number;
  explanation: string | null;
  source: string;
  options: QuestionOption[];
}

export interface StartAttemptResponse {
  id: string;
  assessment_id: string;
  status: AttemptStatus;
  started_at: string;
  duration_minutes: number;
  deadline: string;
  questions: Question[];
}

export interface SavedResponse {
  question_id: string;
  selected_option_ids: string[];
  response_text: string | null;
  marked_for_review: boolean;
  saved: boolean;
}

export interface Attempt {
  id: string;
  assessment_id: string;
  student_id: string;
  started_at: string;
  submitted_at: string | null;
  status: AttemptStatus;
  total_score: number | null;
}

export interface GradedResponse {
  id: string;
  question_id: string;
  response_text: string | null;
  score: number | null;
  is_correct: boolean | null;
  selected_option_ids: string[];
}

export interface AttemptReview {
  attempt: Attempt;
  questions: Question[];
  responses: GradedResponse[];
}

export function listAssessments() {
  return request<Assessment[]>("/assessments", {}, true);
}

export function getAssessment(id: string) {
  return request<Assessment>(`/assessments/${id}`, {}, true);
}

export function createAssessment(data: {
  batch_id: string;
  subject_id: string;
  title: string;
  description?: string;
  duration_minutes: number;
  total_marks: number;
}) {
  return request<Assessment>("/assessments", { method: "POST", body: JSON.stringify(data) }, true);
}

export function listQuestions(assessmentId: string) {
  return request<Question[]>(`/assessments/${assessmentId}/questions`, {}, true);
}

export function addQuestion(
  assessmentId: string,
  data: {
    question_text: string;
    question_type: QuestionType;
    marks: number;
    topic_id?: string;
    difficulty?: string;
    explanation?: string;
    options: { option_text: string; is_correct: boolean }[];
  },
) {
  return request<Question>(`/assessments/${assessmentId}/questions`, { method: "POST", body: JSON.stringify(data) }, true);
}

export function deleteQuestion(assessmentId: string, questionId: string) {
  return request<void>(`/assessments/${assessmentId}/questions/${questionId}`, { method: "DELETE" }, true);
}

export function publishAssessment(id: string) {
  return request<Assessment>(`/assessments/${id}/publish`, { method: "POST" }, true);
}

export function closeAssessment(id: string) {
  return request<Assessment>(`/assessments/${id}/close`, { method: "POST" }, true);
}

export function startAttempt(assessmentId: string) {
  return request<StartAttemptResponse>(`/assessments/${assessmentId}/attempts`, { method: "POST" }, true);
}

export function getAttempt(attemptId: string) {
  return request<Attempt>(`/attempts/${attemptId}`, {}, true);
}

export function listMyResponses(attemptId: string) {
  return request<SavedResponse[]>(`/attempts/${attemptId}/responses`, {}, true);
}

export function submitResponse(
  attemptId: string,
  data: {
    question_id: string;
    selected_option_ids?: string[];
    response_text?: string;
    time_spent_seconds?: number;
    marked_for_review?: boolean;
  },
) {
  return request<SavedResponse>(`/attempts/${attemptId}/responses`, { method: "POST", body: JSON.stringify(data) }, true);
}

export function submitAttempt(attemptId: string) {
  return request<Attempt>(`/attempts/${attemptId}/submit`, { method: "POST" }, true);
}

export function reviewAttempt(attemptId: string) {
  return request<AttemptReview>(`/attempts/${attemptId}/review`, {}, true);
}

export function listAttempts(assessmentId: string) {
  return request<Attempt[]>(`/assessments/${assessmentId}/attempts`, {}, true);
}

export function gradeResponse(assessmentId: string, attemptId: string, questionId: string, score: number) {
  return request<SavedResponse>(
    `/assessments/${assessmentId}/attempts/${attemptId}/responses/${questionId}/grade`,
    { method: "PATCH", body: JSON.stringify({ score }) },
    true,
  );
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export type TrendDirection = "IMPROVING" | "DECLINING" | "STABLE" | "INSUFFICIENT_DATA";

export interface TopicPerformance {
  topic_id: string;
  topic_name: string;
  questions_attempted: number;
  accuracy: number;
  recent_accuracy: number;
  historical_accuracy: number;
  difficulty_adjusted_accuracy: number;
  consistency_score: number;
  mastery_score: number;
  mastery_category: string;
  trend: TrendDirection;
}

export interface StudentPerformance {
  student_id: string;
  overall_mastery: number;
  topics: TopicPerformance[];
  strengths: TopicPerformance[];
  weak_topics: TopicPerformance[];
}

export interface AttentionPanelEntry {
  student_id: string;
  student_name: string;
  topic_id: string;
  topic_name: string;
  mastery_score: number;
  trend: TrendDirection;
}

export interface TopicSummary {
  topic_id: string;
  topic_name: string;
  average_mastery: number;
  median_mastery: number;
  high_mastery: number;
  low_mastery: number;
  student_count: number;
}

export interface ClassPerformance {
  average_score: number | null;
  median_score: number | null;
  high_score: number | null;
  low_score: number | null;
  score_distribution: Record<string, number>;
  average_attendance_percentage: number | null;
  average_mastery: number;
  topics: TopicSummary[];
}

export function getStudentPerformance(studentId: string) {
  return request<StudentPerformance>(`/students/${studentId}/performance`, {}, true);
}

export function getAttentionPanel(batchId: string) {
  return request<AttentionPanelEntry[]>(`/batches/${batchId}/attention-panel`, {}, true);
}

export function getClassPerformance(batchId: string) {
  return request<ClassPerformance>(`/batches/${batchId}/class-performance`, {}, true);
}

// ---------------------------------------------------------------------------
// AI
// ---------------------------------------------------------------------------

export function generateQuestions(data: {
  batch_id: string;
  subject_id: string;
  topic_id?: string;
  grade: string;
  count: number;
  difficulty: string;
  question_types: QuestionType[];
  total_marks: number;
  duration_minutes: number;
}) {
  return request<Assessment>("/ai/generate-questions", { method: "POST", body: JSON.stringify(data) }, true);
}

export function regenerateQuestion(assessmentId: string, questionId: string) {
  return request<Question>(`/ai/assessments/${assessmentId}/questions/${questionId}/regenerate`, { method: "POST" }, true);
}

export function updateQuestion(
  assessmentId: string,
  questionId: string,
  data: { question_text?: string; topic_id?: string; difficulty?: string; marks?: number },
) {
  return request<Question>(`/assessments/${assessmentId}/questions/${questionId}`, { method: "PATCH", body: JSON.stringify(data) }, true);
}

export interface ExtractionJob {
  id: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  assessment_id: string | null;
  error_message: string | null;
}

export function uploadPdfForExtraction(batchId: string, subjectId: string, file: File) {
  const form = new FormData();
  form.set("batch_id", batchId);
  form.set("subject_id", subjectId);
  form.set("file", file);
  return requestForm<ExtractionJob>("/ai/pdf-extract", "POST", form);
}

export function getExtractionJob(jobId: string) {
  return request<ExtractionJob>(`/ai/jobs/${jobId}`, {}, true);
}

export function getStudentTopicInsight(studentId: string, topicId: string) {
  return request<{ insight: string }>(`/ai/students/${studentId}/topics/${topicId}/insight`, {}, true);
}

// ---------------------------------------------------------------------------
// Personalized practice
// ---------------------------------------------------------------------------

export interface PracticeOption {
  id: string;
  option_text: string;
  is_correct: boolean | null;
}

export interface PracticeQuestion {
  id: string;
  question_text: string;
  question_type: QuestionType;
  difficulty: string;
  marks: number;
  order_index: number;
  options: PracticeOption[];
}

export interface PracticeSet {
  id: string;
  topic_id: string;
  topic_name: string;
  title: string;
  difficulty: string;
  status: "IN_PROGRESS" | "COMPLETED";
  mastery_before: number;
  mastery_after: number | null;
  created_at: string;
  completed_at: string | null;
  questions: PracticeQuestion[];
}

export interface PracticeGradedResponse {
  question_id: string;
  selected_option_id: string | null;
  response_text: string | null;
  is_correct: boolean;
  score: number;
}

export interface PracticeCompletion {
  practice_set: PracticeSet;
  responses: PracticeGradedResponse[];
  mastery_before: number;
  mastery_after: number;
  delta: number;
  note: string;
}

export function generatePractice(
  studentId: string,
  topicId: string,
  data: { easy_count?: number; medium_count?: number; hard_count?: number } = {},
) {
  return request<PracticeSet>(`/students/${studentId}/topics/${topicId}/practice`, { method: "POST", body: JSON.stringify(data) }, true);
}

export function getPracticeSet(practiceSetId: string) {
  return request<PracticeSet>(`/practice-sets/${practiceSetId}`, {}, true);
}

export function submitPracticeResponse(
  practiceSetId: string,
  data: { question_id: string; selected_option_id?: string; response_text?: string },
) {
  return request<{ question_id: string; saved: boolean }>(
    `/practice-sets/${practiceSetId}/responses`,
    { method: "POST", body: JSON.stringify(data) },
    true,
  );
}

export function completePracticeSet(practiceSetId: string) {
  return request<PracticeCompletion>(`/practice-sets/${practiceSetId}/complete`, { method: "POST" }, true);
}
