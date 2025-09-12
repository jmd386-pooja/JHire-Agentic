"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/hooks/use-toast";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const CATEGORIES = ["Full Stack", "Data Science", "Data Engineering"];

export default function ResumeInputs() {
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [text, setText] = useState("");

  const { toast } = useToast();

  const [jdModalOpen, setJdModalOpen] = useState(false);
  const [jdStatus, setJdStatus] = useState<
    "idle" | "running" | "complete" | "error"
  >("idle");
  const [jdProgress, setJdProgress] = useState(0);

  // Animate an indeterminate progress while waiting for the response
  useEffect(() => {
    if (jdStatus === "running") {
      setJdProgress(10);
      const id = setInterval(() => {
        setJdProgress((p) => (p >= 90 ? 90 : p + 2));
      }, 200);
      return () => clearInterval(id);
    }
    if (jdStatus === "complete") setJdProgress(100);
    if (jdStatus === "idle" || jdStatus === "error") setJdProgress(0);
  }, [jdStatus]);

  const toggleCategory = (category: string) => {
    setSelectedCategories((prev) =>
      prev.includes(category)
        ? prev.filter((c) => c !== category)
        : [...prev, category]
    );
  };

  const handleButtonClick = async () => {
    // Require at least one category
    if (selectedCategories.length === 0) {
      toast({
        variant: "destructive",
        title: "Select a category",
        description: "Please select at least one category.",
      });
      return;
    }

    // Build the message sent to the agent
    const jdHeader = `This Job Description categories are ${selectedCategories.join(
      ", "
    )}: `;
    const fullJD = jdHeader + (text ?? "");

    // Open progress modal (indeterminate until response)
    setJdModalOpen(true);
    setJdStatus("running");
    setJdProgress(10);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: fullJD }),
      });

      const data = await res.json();

      if (res.ok && data?.status === "success") {
        // Success → complete modal, toast, close
        setJdStatus("complete");
        setJdProgress(100);

        toast({
          title: "Job description processed",
          description: "Ranking completed successfully.",
        });

        // Persist the last submitted JD per selected category
        setInputs((prev) => {
          const updated = { ...prev };
          selectedCategories.forEach((cat) => {
            updated[cat] = text;
          });
          return updated;
        });

        setText("");

        // Auto-close the modal shortly after
        setTimeout(() => setJdModalOpen(false), 800);
      } else {
        const msg = data?.error || data?.warning || "Unknown error";
        setJdStatus("error");
        setJdProgress(0);
        toast({
          variant: "destructive",
          title: "JD processing failed",
          description: msg,
        });
      }
    } catch (e: any) {
      setJdStatus("error");
      setJdProgress(0);
      toast({
        variant: "destructive",
        title: "JD processing failed",
        description: e?.message || String(e),
      });
    }
  };


  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <h2 className="text-3xl font-bold mb-6">Job Descriptions</h2>

      {/* Dropdown styled as a full-width box */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <div className="w-full border rounded-lg p-4 cursor-pointer text-left bg-white hover:bg-gray-50">
            {selectedCategories.length > 0 ? (
              <span>{selectedCategories.join(", ")}</span>
            ) : (
              <span className="text-gray-400 bold p-3">Select Categories</span>
            )}
          </div>
        </DropdownMenuTrigger>

        {/* Dropdown items styled as solid blocks */}
        <DropdownMenuContent className="w-[var(--radix-dropdown-menu-trigger-width)] border rounded-lg shadow-md p-4">
          {CATEGORIES.map((category) => {
            const isSelected = selectedCategories.includes(category);
            return (
              <DropdownMenuCheckboxItem
                key={category}
                checked={isSelected}
                onCheckedChange={() => toggleCategory(category)}
                className={`w-full rounded-lg px-3 pl-8 py-2 mb-3 cursor-pointer font-bold ${
                  isSelected
                    ? "bg-gray-400 text-white"
                    : "bg-gray-100 hover:bg-gray-200 text-gray-800"
                }`}
              >
                {category}
              </DropdownMenuCheckboxItem>
            );
          })}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Shared textarea */}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Enter resume details..."
        className="w-full p-4 border rounded-lg h-40 mt-8"
      />

      <Button onClick={handleButtonClick} className="mt-7">
        Submit
      </Button>

      {/* Summary */}
      <div className="mt-8">
        <h2 className="font-semibold text-2xl mb-2">Descriptions </h2>
        <ul className="list-disc pl-5 space-y-1 text-gray-700">
          {Object.entries(inputs).map(([category, value]) => (
            <li key={category}>
              <strong>{category}:</strong> {value || "No input"}
            </li>
          ))}
        </ul>
      </div>
      <Modal isOpen={jdModalOpen} onClose={() => setJdModalOpen(false)}>
        <div className="p-6 w-[360px] sm:w-[480px]">
          <h2 className="text-xl font-bold mb-3">Processing Job Description</h2>

          <div className="space-y-2">
            <div className="text-sm text-muted-foreground">
              {jdStatus === "running" && "Analyzing and ranking…"}
              {jdStatus === "complete" && "Process complete ✔"}
              {jdStatus === "error" && "An error occurred."}
            </div>

            <Progress value={jdProgress} />
            <div className="text-xs text-muted-foreground">{jdProgress}%</div>
          </div>

          <div className="mt-6 flex justify-end">
            {jdStatus !== "running" && (
              <Button onClick={() => setJdModalOpen(false)}>Close</Button>
            )}
          </div>
        </div>
      </Modal>
    </div>
  );
}
