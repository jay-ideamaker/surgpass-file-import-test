import { useState, type ChangeEvent, useEffect } from "react";
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
  question_bank: string; // Added question_bank field
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

  // Add table styling and image hover functionality
  useEffect(() => {
    // Style all tables with sky blue headers
    const styleAllTables = () => {
      const tables = document.querySelectorAll('table');
      tables.forEach(table => {
        // Style the table
        table.style.width = '100%';
        table.style.borderCollapse = 'collapse';
        table.style.marginTop = '10px';
        table.style.marginBottom = '10px';

        // Style header rows
        const headerRows = table.querySelectorAll('tr:first-child, thead tr');
        headerRows.forEach(row => {
          (row as HTMLElement).style.backgroundColor = '#87CEEB'; // Sky blue
          (row as HTMLElement).style.color = '#000';
          (row as HTMLElement).style.fontWeight = 'bold';
        });

        // Style all cells
        const cells = table.querySelectorAll('td, th');
        cells.forEach(cell => {
          (cell as HTMLElement).style.border = '1px solid #ddd';
          (cell as HTMLElement).style.padding = '8px';
          (cell as HTMLElement).style.textAlign = 'left';
        });
      });
    };

    // Add image hover functionality
    const addImageHoverInfo = () => {
      const images = document.querySelectorAll('img');
      images.forEach(img => {
        // Create hover tooltip for image source
        img.style.cursor = 'pointer';
        img.title = `Image source: ${img.src}`;

        // Add click functionality to open image in new tab
        img.addEventListener('click', () => {
          window.open(img.src, '_blank');
        });

        // Look for image source information in nearby text
        const parent = img.parentElement;
        if (parent) {
          const nextElements = Array.from(parent.parentElement?.children || []);
          const currentIndex = nextElements.indexOf(parent);

          // Look for "Image Source:" or similar text in following elements
          for (let i = currentIndex + 1; i < Math.min(currentIndex + 5, nextElements.length); i++) {
            const element = nextElements[i];
            const text = element.textContent || '';

            if (text.toLowerCase().includes('image source:') || text.toLowerCase().includes('from:')) {
              // Extract the source info and add it to the title
              const sourceText = text.replace(/image source:/i, '').replace(/from:/i, '').trim();
              img.title = `${img.title}\n\nSource: ${sourceText}`;

              // Look for URLs in the source text and make them clickable
              const urlMatch = sourceText.match(/(https?:\/\/[^\s\)]+)/);
              if (urlMatch) {
                const url = urlMatch[1];
                img.style.border = '2px solid #007bff';
                img.title = `${img.title}\n\nClick to view source: ${url}`;

                // Override click to go to source instead of just the image
                img.removeEventListener('click', () => window.open(img.src, '_blank'));
                img.addEventListener('click', () => {
                  window.open(url, '_blank');
                });
              }
              break;
            }
          }
        }
      });
    };

    // Apply styling after a short delay to ensure content is rendered
    const timer = setTimeout(() => {
      styleAllTables();
      addImageHoverInfo();
    }, 100);

    return () => clearTimeout(timer);
  }, [processedQuestions]); // Re-run when questions change

  const fetchQuestionsByIds = async (ids: string[]) => {
    if (!ids || ids.length === 0) return;

    // The new, simpler query targeting our view
    const { data, error } = await supabase
      .from('questions_with_all_relations') // <-- Use the new view if it exists
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
              {q.question_bank && <span className="question-bank-badge">{q.question_bank}</span>}
              {q.subject}: {q.topic}
            </h3>
            <div className="metadata">
              <span>
                <strong>Blueprint:</strong> {q.blueprint}
              </span>
              {q.difficulty && (
                <span>
                  <strong>Difficulty:</strong> {q.difficulty}
                </span>
              )}
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

            {q.articles && q.articles.length > 0 && (
              <>
                <h4>References</h4>
                <div className="references">
                  {q.articles.map((article, i) => (
                    <p key={i} className="reference-item">
                      {article.text}
                    </p>
                  ))}
                </div>
              </>
            )}

            {q.quick_hits && q.quick_hits.length > 0 && (
              <>
                <h4>QuickHits</h4>
                <div className="quickhits">
                  {q.quick_hits.map((qh, i) => (
                    <div key={i} className="quickhit-item">
                      <p><strong>Question:</strong> {qh.question_text}</p>
                      {qh.answers.map((ans, j) => (
                        <div key={j} className={`quickhit-answer ${ans.is_correct ? 'correct' : ''}`}>
                          {ans.text}
                        </div>
                      ))}
                      <p><strong>Rationale:</strong> {qh.rationale}</p>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;