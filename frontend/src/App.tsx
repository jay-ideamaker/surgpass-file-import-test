import { useState, type ChangeEvent, } from "react";
import axios from "axios";
import { supabase } from "./supabaseClient";
import "./App.css";

// --- TypeScript Interfaces ---
interface Tag { name: string; }
interface AnswerChoice { text: string; is_correct: boolean; explanation: string; }
interface Article { text: string; }
interface QuickHitAnswer { text: string; is_correct: boolean; }
interface QuickHit { question_text: string; rationale: string; answers: QuickHitAnswer[]; }
interface Question {
  id: string;
  blueprint: string;
  subject: string;
  topic: string;
  difficulty: number;
  tags: Tag[];
  question_text: string;
  short_explanation: string;
  full_explanation: string;
  answer_choices: AnswerChoice[];
  articles: Article[];
  quick_hits: QuickHit[];
}

// --- API Response Types ---
interface UploadSuccessResponse {
  message: string;
  question_ids: string[];
}

function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processedQuestions, setProcessedQuestions] = useState<Question[]>([]);
  const [error, setError] = useState<string>("");
  const [successMessage, setSuccessMessage] = useState("");

  const fetchQuestionsByIds = async (ids: string[]) => {
    if (!ids || ids.length === 0) return;

    // The new, simpler query targeting our view
    const { data, error } = await supabase
      .from('questions_with_all_relations') // <-- Use the new view
      .select('*') // <-- Select everything, the view has all the data!
      .in('id', ids);

    if (error) {
      setError(`Failed to fetch processed data from Supabase: ${error.message}`);
    } else if (data) {
      setProcessedQuestions(data as any);
    }
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setSelectedFile(event.target.files[0]);
      setProcessedQuestions([]);
      setError("");
      setSuccessMessage("");
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError("Please select a file first.");
      return;
    }
    setIsProcessing(true);
    setError("");
    setProcessedQuestions([]);
    setSuccessMessage("");

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await axios.post<UploadSuccessResponse>(
        "http://127.0.0.1:8000/api/upload/",
        formData
      );
      setSuccessMessage(response.data.message);
      await fetchQuestionsByIds(response.data.question_ids);
    } catch (err: any) {
      setError("Upload failed. " + (err.response?.data?.error || err.message));
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="App" style={{ backgroundColor: 'white' }}>
      <header className="App-header">
        <h1>SurgPass File Import Prototype</h1>
        <p>
          Upload a filled-out .doc template to see the fully parsed and
          rendered result.
        </p>
        <div className="controls">
          <input type="file" onChange={handleFileChange} accept=".docx" />
          <button onClick={handleUpload} disabled={isProcessing}>
            {isProcessing ? "Processing..." : "Upload and Process"}
          </button>
        </div>
        {error && <p className="error-box">{error}</p>}
      </header>

      <div className="results-container">
        {successMessage && !isProcessing && <h2>✅ {successMessage}</h2>}
        {processedQuestions.map((q) => (
          <div key={q.id} className="question-card">
            <h3>
              {q.subject}: {q.topic}
            </h3>
            <div className="metadata">
              <span>
                <strong>Blueprint:</strong> {q.blueprint}
              </span>
              <span>
                <strong>Difficulty:</strong> {q.difficulty}
              </span>
              <div className="tags">
                {q.tags.map((tag) => (
                  <span key={tag.name} className="tag">
                    {tag.name}
                  </span>
                ))}
              </div>
            </div>

            <h4>Question Text</h4>
            <div
              className="content-block"
              dangerouslySetInnerHTML={{ __html: q.question_text }}
            />

            <h4>Explanations</h4>
            <div
              className="content-block"
              dangerouslySetInnerHTML={{ __html: q.short_explanation }}
            />
            <div
              className="content-block"
              dangerouslySetInnerHTML={{ __html: q.full_explanation }}
            />

            <h4>Answer Choices</h4>
            {q.answer_choices.map((ans, i) => (
              <div
                key={i}
                className={`answer-choice ${ans.is_correct ? "correct" : ""}`}
              >
                <p>
                  <strong>Answer:</strong> {ans.text}
                </p>
                <p>
                  <strong>Explanation:</strong> {ans.explanation}
                </p>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;