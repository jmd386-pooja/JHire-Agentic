
// "use client";
// import { useState } from "react";
// import { Users, Calendar, Clock } from "lucide-react";
// import { Button } from "@/components/ui/button";



// const CATEGORIES = ["Full Stack", "Data Science", "Data Engineering"];

// export default function ResumeInputs() {
//   // State type: a dictionary where keys are strings (categories), values are strings (input text)
//   const [inputs, setInputs] = useState<Record<string, string>>({});

//   const handleChange = (category: string, value: string) => {
//     setInputs((prev) => ({
//       ...prev,
//       [category]: value,
//     }));
//   };

//     const handleButtonClick = (category: string) => {
//     alert(`Submitted for ${category}: ${inputs[category] || "No input"}`);
//     // Replace the 
//     // alert with any function (e.g., API call, state update)
//   };
//   return (

//     <div className="flex-1 space-y-6 overflow-y-auto p-8 pt-3 relative max-w-7xl mx-auto w-full grid gap-4 p-4">
//       <h2 className="text-3xl font-bold px-4 pt-4">Job Descriptions</h2>
//       {CATEGORIES.map((category) => (
//         <div
//           key={category}
//           className="p-4 rounded-2xl shadow-md border border-gray-200"
//         >
//           <h2 className="text-lg font-semibold mb-2">{category}</h2>
//           <textarea
//             value={inputs[category] || ""}
//             onChange={(e) => handleChange(category, e.target.value)}
//             placeholder={`Enter resume details for ${category}`}
//             className="w-full p-2 border rounded-lg"
//           />
//             <Button
//               onClick={() => handleButtonClick(category)}
//               className="mt-2"
//             >
//             Submit
//             </Button>

//       </div>

//       ))}

//         <footer>
//           <div className="max-w-7xl mx-auto flex justify-between items-center">
//           <p className="text-sm text-gray-600 m-0">© 2024 JMAN, All Rights Reserved</p>
//           {/* <Image
//             src={JmanLogo}
//             alt="JMAN Logo"
//             width={120}
//             height={40}
//             className="m-0"
//           /> */}
//         </div>
//         </footer>      
//     </div>
//   );
// }



// "use client";
// import { useState } from "react";
// import { Button } from "@/components/ui/button";

// const CATEGORIES = ["Full Stack", "Data Science", "Data Engineering"];

// export default function ResumeInputs() {
//   // Track which categories are selected
//   const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
//   // Store input per category
//   const [inputs, setInputs] = useState<Record<string, string>>({});
//   // Text in shared textarea
//   const [text, setText] = useState("");

//   // Handle checkbox toggle
//   const handleCategoryToggle = (category: string) => {
//     setSelectedCategories((prev) =>
//       prev.includes(category)
//         ? prev.filter((c) => c !== category)
//         : [...prev, category]
//     );
//   };

//   // Submit: apply textarea content to all selected categories
//   const handleButtonClick = () => {
//     if (selectedCategories.length === 0) {
//       alert("Please select at least one category.");
//       return;
//     }

//     setInputs((prev) => {
//       const updated = { ...prev };
//       selectedCategories.forEach((cat) => {
//         updated[cat] = text;
//       });
//       return updated;
//     });

//     alert(
//       `Submitted:\n${selectedCategories
//         .map((cat) => `${cat}: ${text || "No input"}`)
//         .join("\n")}`
//     );

//     // Clear textarea after submit (optional)
//     setText("");
//   };

//   return (
//     <div className="min-h-screen bg-white">
//       <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
//         <h2 className="text-3xl font-bold mb-6">Job Descriptions</h2>

//         {/* Checkboxes */}
//         <div className="mb-4 space-y-2">
//           <p className="font-medium mb-2">Select Categories:</p>
//           {CATEGORIES.map((category) => (
//             <label key={category} className="flex items-center space-x-2">
//               <input
//                 type="checkbox"
//                 checked={selectedCategories.includes(category)}
//                 onChange={() => handleCategoryToggle(category)}
//                 className="h-4 w-4"
//               />
//               <span>{category}</span>
//             </label>
//           ))}
//         </div>

//         {/* Shared textarea */}
//         <textarea
//           value={text}
//           onChange={(e) => setText(e.target.value)}
//           placeholder="Job Descriptions.."
//           className="w-full p-2 border rounded-lg h-40"
//         />

//         <Button onClick={handleButtonClick} className="mt-3">
//           Submit
//         </Button>

//         {/* Debug / summary view */}
//         <div className="mt-6">
//           <h3 className="font-semibold mb-2">Stored Inputs</h3>
//           <ul className="list-disc pl-5 space-y-1 text-gray-700">
//             {Object.entries(inputs).map(([category, value]) => (
//               <li key={category}>
//                 <strong>{category}:</strong> {value || "No input"}
//               </li>
//             ))}
//           </ul>
//         </div>

//         {/* Footer */}
//         <footer className="mt-10 border-t pt-4">
//           <div className="flex justify-between items-center">
//             <p className="text-sm text-gray-600">
//               © 2024 JMAN, All Rights Reserved
//             </p>
//           </div>
//         </footer>
//       </div>
//     </div>
//   );
// }



"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
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

  const toggleCategory = (category: string) => {
    setSelectedCategories((prev) =>
      prev.includes(category)
        ? prev.filter((c) => c !== category)
        : [...prev, category]
    );
  };

  const handleButtonClick = () => {
    if (selectedCategories.length === 0) {
      alert("Please select at least one category.");
      return;
    }

    setInputs((prev) => {
      const updated = { ...prev };
      selectedCategories.forEach((cat) => {
        updated[cat] = text;
      });
      return updated;
    });

    alert(
      `Submitted:\n${selectedCategories
        .map((cat) => `${cat}: ${text || "No input"}`)
        .join("\n")}`
    );

    setText(""); // optional clear
  };

  return (
    <div className="min-h-screen bg-white">
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

        <Button onClick={handleButtonClick} className="mt-3">
          Submit
        </Button>

        {/* Summary */}
        <div className="mt-8">
          <h2 className="font-semibold text-2xl mb-2">Stored Inputs</h2>
          <ul className="list-disc pl-5 space-y-1 text-gray-700">
            {Object.entries(inputs).map(([category, value]) => (
              <li key={category}>
                <strong>{category}:</strong> {value || "No input"}
              </li>
            ))}
          </ul>
        </div>

        {/* Footer */}
        <footer className="mt-10 border-t pt-4">
          <div className="flex justify-between items-center">
            <p className="text-sm text-gray-600">
              © 2024 JMAN, All Rights Reserved
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
}
