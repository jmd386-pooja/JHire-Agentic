"use client";

import React, { useState, useRef } from "react";
import { Modal } from "@/components/ui/modal"; // Ensure you have a Modal component implemented
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { UploadCloud, XCircle } from "lucide-react";

const ResumeForm: React.FC = () => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [collegeName, setCollegeName] = useState<string>("");
  const [examDateTime, setExamDateTime] = useState<string>(""); // Stores both date and time
  const [expiryDateTime, setExpiryDateTime] = useState<string>(""); // Stores expiry date and time
  const [loading, setLoading] = useState<boolean>(false);
  const [success, setSuccess] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const { toast } = useToast();

  // Progress modal and streaming state
  const [isProgressOpen, setIsProgressOpen] = useState(false);
  const [totalFiles, setTotalFiles] = useState(0);
  const [processedCount, setProcessedCount] = useState(0);
  const [status, setStatus] = useState<
    "idle" | "running" | "categorizing" | "complete" | "error"
  >("idle");
  const [lastFiles, setLastFiles] = useState<string[]>([]);
  const appendFile = (name: string) =>
    setLastFiles((prev) => [name, ...prev].slice(0, 5));

  const handleFetchFromSharePoint = async () => {
    try {
      setIsProgressOpen(true);
      setStatus("running");
      setProcessedCount(0);
      setTotalFiles(0);
      setLastFiles([]);

      const res = await fetch("/api/fetchSharepointResumes", {
        cache: "no-store",
      });
      if (!res.body) throw new Error("No response body");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const showPerItemToast = () => !isProgressOpen;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf("\n")) >= 0) {
          const line = buffer.slice(0, idx).trim();
          buffer = buffer.slice(idx + 1);
          if (!line) continue;
          try {
            const evt = JSON.parse(line);
            if (evt.type === "start") {
              setTotalFiles(evt.total || 0);
            } else if (evt.type === "item") {
              setProcessedCount(evt.index || 0);
              if (evt.file) {
                appendFile(evt.file);
                if (showPerItemToast())
                  toast({ title: "Resume processed", description: evt.file });
              }
            } else if (evt.type === "categorizing") {
              setStatus("categorizing");
            } else if (evt.type === "complete") {
              setStatus("complete");
              window.dispatchEvent(new Event("candidates:refresh"));
              if (!isProgressOpen)
                toast({
                  title: "Done",
                  description: `Fetched & categorized ${
                    evt.total ?? processedCount
                  } resumes.`,
                });
              setTimeout(() => setIsProgressOpen(false), 800);
            } else if (evt.type === "error") {
              setStatus("error");
              toast({
                variant: "destructive",
                title: "Error",
                description: evt.message || "Failed while fetching resumes.",
              });
              setIsProgressOpen(false);
            }
          } catch {}
        }
      }
    } catch (e: any) {
      setStatus("error");
      toast({
        variant: "destructive",
        title: "Error",
        description: e?.message || "Failed to start SharePoint fetch.",
      });
      setIsProgressOpen(false);
    }
  };

  // Handle file selection
  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files) return;

    const validFiles = Array.from(files).filter(
      (file) => file.type === "application/pdf"
    );
    if (validFiles.length !== files.length) {
      setError("Only PDF files are allowed.");
      return;
    }

    setSelectedFiles((prevFiles) => [...prevFiles, ...validFiles]);
    setError(null);
  };

  const handleFileRemove = (index: number) => {
    setSelectedFiles((prevFiles) => prevFiles.filter((_, i) => i !== index));
  };

  const formatLocalDateTime = (dateTime: string): string => {
    const date = new Date(dateTime);
    const localYear = date.getFullYear();
    const localMonth = String(date.getMonth() + 1).padStart(2, "0");
    const localDate = String(date.getDate()).padStart(2, "0");
    const localHours = String(date.getHours()).padStart(2, "0");
    const localMinutes = String(date.getMinutes()).padStart(2, "0");
    return `${localYear}-${localMonth}-${localDate}T${localHours}:${localMinutes}`;
  };

  // Submit handler for uploading resumes and registering the college with date/time
  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (selectedFiles.length === 0) {
      setError("Please upload at least one PDF resume.");
      return;
    }

    if (!collegeName || !examDateTime || !expiryDateTime) {
      setError("Please fill in all the fields.");
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(false);

    const formData = new FormData();
    selectedFiles.forEach((file) => {
      formData.append("files", file);
    });
    formData.append("college", collegeName);
    formData.append("examDateTime", formatLocalDateTime(examDateTime));
    formData.append("expiryDateTime", formatLocalDateTime(expiryDateTime));

    try {
      const response = await fetch("/api/extractResumeDetails", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorResponse = await response.json();
        setError(errorResponse.error || "Failed to process resumes.");
        setLoading(false);
        return;
      }

      const result = await response.json();

      setSuccess(true);
      setSelectedFiles([]);
      setCollegeName("");
      setExamDateTime("");
      setExpiryDateTime("");
      if (fileInputRef.current) fileInputRef.current.value = "";

      toast({
        title: "Upload Successful",
        description:
          result.message || "Resumes uploaded and processed successfully.",
      });

      // Refresh the candidates table
      window.dispatchEvent(new Event("candidates:refresh"));
    } catch (err) {
      console.error("Error uploading resumes:", err);
      setError("An error occurred while uploading resumes.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-7 space-y-6">
      <div className="flex flex-col lg:flex-row lg:justify-end items-center">
        <Button
          onClick={() => setIsModalOpen(true)}
          style={{
            backgroundColor: "#19105B",
            color: "white",
            marginRight: "10px",
          }}
          className="px-4 py-2 rounded flex items-center lg:relative lg:top-0 lg:right-4 lg:ml-auto"
        >
          &#43; Upload Resumes
        </Button>

        <Button
          onClick={handleFetchFromSharePoint}
          style={{ backgroundColor: "#19105B", color: "white" }}
          className="px-4 py-2 ms-3 rounded flex items-center lg:relative lg:top-0 lg:right-4 lg:ml-auto"
        >
          &#43; Fetch Resumes from Share Point
        </Button>
      </div>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)}>
        <div className="p-6">
          <h2 className="text-xl font-bold mb-4">Upload Resumes</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* College Name */}
            <div>
              <label className="block text-sm font-medium mb-2">
                College Name
              </label>
              <Input
                type="text"
                value={collegeName}
                onChange={(e) => setCollegeName(e.target.value)}
                placeholder="Enter college name"
                className="w-full"
                required
              />
            </div>

            {/* Exam Date & Time */}
            <div>
              <label className="block text-sm font-medium mb-2">
                Exam Date & Time
              </label>
              <Input
                type="datetime-local"
                value={examDateTime}
                onChange={(e) => setExamDateTime(e.target.value)}
                className="w-full"
                required
              />
            </div>

            {/* Expiry Date & Time */}
            <div>
              <label className="block text-sm font-medium mb-2">
                Expiry Date & Time
              </label>
              <Input
                type="datetime-local"
                value={expiryDateTime}
                onChange={(e) => setExpiryDateTime(e.target.value)}
                className="w-full"
                required
              />
            </div>

            {/* File Upload */}
            <div>
              <label className="block text-sm font-medium mb-2">
                Upload Files
              </label>
              <div className="border-2 border-dashed rounded-md p-4 bg-gray-50">
                <input
                  type="file"
                  accept="application/pdf"
                  multiple
                  onChange={handleFileUpload}
                  ref={fileInputRef}
                  className="hidden"
                  id="file-upload"
                />
                <label
                  htmlFor="file-upload"
                  className="flex items-center justify-center gap-2 text-blue-600 cursor-pointer"
                >
                  <UploadCloud className="w-5 h-5" />
                  <span>Click to upload PDF files</span>
                </label>

                {selectedFiles.length > 0 && (
                  <div className="mt-4 space-y-2">
                    {selectedFiles.map((file, index) => (
                      <div
                        key={index}
                        className="flex items-center justify-between bg-white p-2 rounded-md shadow-sm"
                      >
                        <span className="text-sm truncate">{file.name}</span>
                        <button
                          type="button"
                          onClick={() => handleFileRemove(index)}
                          className="text-red-500 hover:text-red-700"
                        >
                          <XCircle className="w-5 h-5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Error or Success Message */}
            {error && (
              <div className="mt-4 p-2 text-red-600 bg-red-50 border border-red-200 rounded">
                {error}
              </div>
            )}
            {success && (
              <div className="mt-4 p-2 text-green-600 bg-green-50 border border-green-200 rounded">
                Resumes uploaded successfully!
              </div>
            )}

            {/* Submit Button */}
            <div className="mt-4 flex justify-end">
              <Button
                type="submit"
                disabled={loading}
                style={{ backgroundColor: "#19105B", color: "white" }}
                className="px-4 py-2 rounded"
              >
                {loading ? "Uploading..." : "Upload & Process"}
              </Button>
            </div>
          </form>
        </div>
      </Modal>

      {/* Progress Modal for SharePoint Fetch */}
      <Modal isOpen={isProgressOpen} onClose={() => setIsProgressOpen(false)}>
        <div className="p-6 w-[360px] sm:w-[480px]">
          <h2 className="text-xl font-bold mb-3">Fetching from SharePoint</h2>
          <div className="space-y-2 mb-4">
            <div className="text-sm text-muted-foreground">
              {status === "running" && "Downloading & parsing resumes..."}
              {status === "categorizing" && "Categorizing candidates..."}
              {status === "complete" && "Process complete ✔"}
              {status === "error" && "An error occurred."}
            </div>
            <Progress
              value={
                totalFiles
                  ? Math.round((processedCount / Math.max(totalFiles, 1)) * 100)
                  : 0
              }
            />
            <div className="text-xs text-muted-foreground">
              {processedCount} / {totalFiles} processed
            </div>
          </div>

          {lastFiles.length > 0 && (
            <div className="mt-2">
              <div className="text-sm font-medium mb-1">Recent:</div>
              <ul className="text-xs space-y-1 max-h-24 overflow-auto pr-1">
                {lastFiles.map((f, i) => (
                  <li key={i} className="truncate">
                    • {f}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-6 flex justify-end gap-2">
            {status !== "complete" && (
              <Button
                variant="secondary"
                onClick={() => setIsProgressOpen(false)}
              >
                Hide
              </Button>
            )}
            {status === "complete" && (
              <Button onClick={() => setIsProgressOpen(false)}>Close</Button>
            )}
          </div>
        </div>
      </Modal>

      {/* Success message outside modal */}
      {success && (
        <div className="mt-6 p-4 bg-green-100 text-green-700 border border-green-300 rounded-md text-center">
          Registered Successfully!
        </div>
      )}
    </div>
  );
};

export default ResumeForm;
