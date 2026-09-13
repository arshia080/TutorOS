"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ErrorBanner } from "@/components/error-banner";
import { addQuestion, type QuestionType, ApiError } from "@/lib/api";

const QUESTION_TYPES: { value: QuestionType; label: string }[] = [
  { value: "MCQ", label: "Multiple choice (single answer)" },
  { value: "MULTI_SELECT", label: "Multiple choice (multi-select)" },
  { value: "TRUE_FALSE", label: "True / False" },
  { value: "NUMERICAL", label: "Numerical" },
  { value: "SHORT_ANSWER", label: "Short answer (manually graded)" },
  { value: "LONG_ANSWER", label: "Long answer (manually graded)" },
];

interface OptionDraft {
  option_text: string;
  is_correct: boolean;
}

export function QuestionForm({ assessmentId, onAdded }: { assessmentId: string; onAdded: () => void }) {
  const [questionType, setQuestionType] = useState<QuestionType>("MCQ");
  const [questionText, setQuestionText] = useState("");
  const [marks, setMarks] = useState("1");
  const [options, setOptions] = useState<OptionDraft[]>([
    { option_text: "", is_correct: false },
    { option_text: "", is_correct: false },
  ]);
  const [numericAnswer, setNumericAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const needsOptions = questionType === "MCQ" || questionType === "MULTI_SELECT";
  const isTrueFalse = questionType === "TRUE_FALSE";
  const isNumerical = questionType === "NUMERICAL";
  const isSubjective = questionType === "SHORT_ANSWER" || questionType === "LONG_ANSWER";

  function updateOptionText(index: number, text: string) {
    setOptions((prev) => prev.map((o, i) => (i === index ? { ...o, option_text: text } : o)));
  }

  function setSingleCorrect(index: number) {
    setOptions((prev) => prev.map((o, i) => ({ ...o, is_correct: i === index })));
  }

  function toggleCorrect(index: number) {
    setOptions((prev) => prev.map((o, i) => (i === index ? { ...o, is_correct: !o.is_correct } : o)));
  }

  function addOption() {
    setOptions((prev) => [...prev, { option_text: "", is_correct: false }]);
  }

  function removeOption(index: number) {
    setOptions((prev) => prev.filter((_, i) => i !== index));
  }

  function resetForm() {
    setQuestionText("");
    setMarks("1");
    setOptions([
      { option_text: "", is_correct: false },
      { option_text: "", is_correct: false },
    ]);
    setNumericAnswer("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      let finalOptions: OptionDraft[] = [];
      if (isTrueFalse) {
        finalOptions = [
          { option_text: "True", is_correct: options[0]?.is_correct ?? false },
          { option_text: "False", is_correct: options[1]?.is_correct ?? false },
        ];
      } else if (isNumerical) {
        finalOptions = [{ option_text: numericAnswer, is_correct: true }];
      } else if (needsOptions) {
        finalOptions = options.filter((o) => o.option_text.trim().length > 0);
      }

      await addQuestion(assessmentId, {
        question_text: questionText,
        question_type: questionType,
        marks: Number(marks),
        options: finalOptions,
      });
      resetForm();
      onAdded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add question");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="space-y-1">
        <Label>Question type</Label>
        <Select value={questionType} onValueChange={(v: string | null) => v && setQuestionType(v as QuestionType)}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {QUESTION_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1">
        <Label htmlFor="question_text">Question</Label>
        <Textarea id="question_text" required value={questionText} onChange={(e) => setQuestionText(e.target.value)} />
      </div>

      <div className="space-y-1 max-w-[120px]">
        <Label htmlFor="marks">Marks</Label>
        <Input id="marks" type="number" min={1} step="0.5" required value={marks} onChange={(e) => setMarks(e.target.value)} />
      </div>

      {isTrueFalse && (
        <div className="space-y-1">
          <Label>Correct answer</Label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input type="radio" name="tf" checked={options[0]?.is_correct ?? false} onChange={() => setSingleCorrect(0)} />
              True
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="radio" name="tf" checked={options[1]?.is_correct ?? false} onChange={() => setSingleCorrect(1)} />
              False
            </label>
          </div>
        </div>
      )}

      {isNumerical && (
        <div className="space-y-1 max-w-[200px]">
          <Label htmlFor="numeric_answer">Correct numeric answer</Label>
          <Input
            id="numeric_answer"
            type="number"
            step="any"
            required
            value={numericAnswer}
            onChange={(e) => setNumericAnswer(e.target.value)}
          />
        </div>
      )}

      {needsOptions && (
        <div className="space-y-2">
          <Label>Options (mark the correct {questionType === "MCQ" ? "answer" : "answers"})</Label>
          {options.map((opt, i) => (
            <div key={i} className="flex items-center gap-2">
              {questionType === "MCQ" ? (
                <input type="radio" name="mcq-correct" checked={opt.is_correct} onChange={() => setSingleCorrect(i)} />
              ) : (
                <input type="checkbox" checked={opt.is_correct} onChange={() => toggleCorrect(i)} />
              )}
              <Input
                value={opt.option_text}
                placeholder={`Option ${i + 1}`}
                onChange={(e) => updateOptionText(i, e.target.value)}
              />
              {options.length > 2 && (
                <Button type="button" variant="ghost" size="sm" onClick={() => removeOption(i)}>
                  Remove
                </Button>
              )}
            </div>
          ))}
          <Button type="button" variant="outline" size="sm" onClick={addOption}>
            Add option
          </Button>
        </div>
      )}

      {isSubjective && (
        <p className="text-sm text-muted-foreground">
          This question has no options -- a teacher grades it manually after submission.
        </p>
      )}

      {error && <ErrorBanner message={error} />}
      <Button type="submit" disabled={submitting}>
        {submitting ? "Adding..." : "Add question"}
      </Button>
    </form>
  );
}
