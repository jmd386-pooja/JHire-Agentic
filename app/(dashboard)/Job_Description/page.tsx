
"use client";
import { useState } from "react";
import { Users, Calendar, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";



const CATEGORIES = ["Full Stack", "Data Science", "Data Engineering"];

export default function ResumeInputs() {
  // State type: a dictionary where keys are strings (categories), values are strings (input text)
  const [inputs, setInputs] = useState<Record<string, string>>({});

  const handleChange = (category: string, value: string) => {
    setInputs((prev) => ({
      ...prev,
      [category]: value,
    }));
  };

    const handleButtonClick = (category: string) => {
    alert(`Submitted for ${category}: ${inputs[category] || "No input"}`);
    // Replace the 
    // alert with any function (e.g., API call, state update)
  };
  return (

    <div className="flex-1 space-y-6 overflow-y-auto p-8 pt-3 relative max-w-7xl mx-auto w-full grid gap-4 p-4">
      <h2 className="text-3xl font-bold px-4 pt-4">Job Descriptions</h2>
      {CATEGORIES.map((category) => (
        <div
          key={category}
          className="p-4 rounded-2xl shadow-md border border-gray-200"
        >
          <h2 className="text-lg font-semibold mb-2">{category}</h2>
          <textarea
            value={inputs[category] || ""}
            onChange={(e) => handleChange(category, e.target.value)}
            placeholder={`Enter resume details for ${category}`}
            className="w-full p-2 border rounded-lg"
          />
            <Button
              onClick={() => handleButtonClick(category)}
              className="mt-2"
            >
            Submit
            </Button>

      </div>

      ))}

        <footer>
          <div className="max-w-7xl mx-auto flex justify-between items-center">
          <p className="text-sm text-gray-600 m-0">© 2024 JMAN, All Rights Reserved</p>
          {/* <Image
            src={JmanLogo}
            alt="JMAN Logo"
            width={120}
            height={40}
            className="m-0"
          /> */}
        </div>
        </footer>      
    </div>
  );
}
