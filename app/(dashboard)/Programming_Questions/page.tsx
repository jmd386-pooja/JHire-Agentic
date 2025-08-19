"use client";

import { useEffect, useState } from "react";
import axios from "axios";
import { useRouter } from "next/navigation";
import Pagination from "@mui/material/Pagination";
import { Eye, Trash2 } from 'lucide-react';
import { toast, ToastContainer } from "react-toastify";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Loader } from '@/components/ui/loader'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { ScrollArea } from "@/components/ui/scroll-area"
import IconCloud from "@/components/ui/icon-cloud";
import jman from '@/images/Jman.png'
import { BorderBeam } from "@/components/ui/border-beam";
import Image from "next/image";
import FooterImage from "@/images/JMANLogoBlue.png"
const slugs = [
  
  "typescript",
  "javascript",
  "dart",
  "java",
  "react",
  "html5",
  "css3",
  "express",
  "nextdotjs",
  "prisma",
  "amazonaws",
  "postgresql",
  "firebase",
  "nginx",
  "vercel",
  "testinglibrary",
  "docker",
  "git",
  "github",
  "gitlab",
  "visualstudiocode",
  "figma",
];
// Define types for the question and test cases
type TestCase = {
  input: string;
  output: string;
  explanation: string; // Added explanation field
};

type Question = {
  id: string;
  title: string; // Added title field
  question: string;
  // difficulty: "Easy" | "Medium" | "Hard";
  constraints: string[];
  testcases: TestCase[];
  internalTestCases: TestCase[];
};

export default function QuestionsPage() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [selectedQuestion, setSelectedQuestion] = useState<Question | null>(null);
  const [isCardVisible, setIsCardVisible] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const[isLoader,setIsLoader]=useState(false);

  // Pagination states
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5; // Items per page

  const fetchQuestions = async () => {
    setIsLoader(true);
    try {
      const response = await axios.get("/api/Programming_Questions");
      setQuestions(response.data);
    } catch (error) {
      console.error("Error fetching questions:", error);
    }finally{
      setIsLoader(false);
    }
  };

  useEffect(() => {
    fetchQuestions();
  }, []);

  const openCard = (question: Question) => {
    setSelectedQuestion({ ...question });
    setIsCardVisible(true);
    setIsEditing(false);
    setErrorFields({
      title: false,
      question: false,
      testcases: false,
      internalTestCases: false,
    });
  };

  const closeCard = () => {
    setSelectedQuestion(null);
    setIsCardVisible(false);
    setIsEditing(false);
    fetchQuestions();
    setErrorFields({
      title: false,
      question: false,
      testcases: false,
      internalTestCases: false,
    });
  };

  const handleEdit = () => {
    setIsEditing(true);
  };

  const [errorFields, setErrorFields] = useState({
    title: false,
    question: false,
    testcases: false,
    internalTestCases: false,
  });
  
  const handleSave = async () => {
    if (!selectedQuestion) return;
    // Initialize error fields tracker
    const newErrorFields = {
      title: false,
      question: false,
      testcases: false,
      internalTestCases: false,
    };
  
    const { title, question, testcases = [], internalTestCases = [] } = selectedQuestion;
  
    // Validation logic
    let isValid = true;
    if (!title.trim()) {
      newErrorFields.title = true;
      isValid = false;
    }
    if (!question.trim()) {
      newErrorFields.question = true;
      isValid = false;
    }
  
    const validateTestCases = (
      cases: { input: string; output: string; explanation?: string }[],
      type: "testcases" | "internalTestCases"
    ) => {
      let hasError = false;
      cases.forEach((testcase) => {
        if (!testcase.input.trim() || !testcase.output.trim()) {
          hasError = true;
        }
        if (type === "testcases" && !testcase.explanation?.trim()) {
          hasError = true;
        }
      });
      if (hasError) {
        newErrorFields[type] = true;
        isValid = false;
      }
    };
  
    validateTestCases(testcases, "testcases");
    validateTestCases(internalTestCases, "internalTestCases");
  
    // Update error fields state for highlighting
    setErrorFields(newErrorFields);
  
    if (!isValid) return; // Exit if there are validation errors
    setIsLoading(true);
    // Preparing payload for the API
    try {
      const { testcases, internalTestCases, ...questionData } = selectedQuestion;
      const payload = {
        ...questionData,
        testcases: testcases.map(({ input, output, explanation }) => ({ input, output, explanation })),
        internalTestCases: internalTestCases.map(({ input, output }) => ({ input, output })), // No explanation for internalTestCases
      };
  
      // Sending the updated data
      await axios.patch("/api/Programming_Questions", payload);
      toast.success("Question updated successfully!", { autoClose: 2000 });
      closeCard();
      fetchQuestions(); // Refresh the list of questions
    } catch (error) {
      console.error("Error updating question:", error);
      toast.error("Failed to update question.", { autoClose: 2000 });
    }finally{
      setIsLoading(false);
    }
  };
  
  // Highlight invalid fields
  const getBorderClass = (field: keyof typeof errorFields) =>
    errorFields[field] ? "border-slate-800 border-2" : "";
  
  const handleAddTestCase = (type: "testcases" | "internalTestCases") => {
    if (selectedQuestion) {
      const updatedQuestion = { ...selectedQuestion };
      updatedQuestion[type] = [...updatedQuestion[type], { input: "", output: "", explanation: "" }];
      setSelectedQuestion(updatedQuestion);
    }
  };

  const handleRemoveTestCase = (type: "testcases" | "internalTestCases", index: number) => {
    if (selectedQuestion) {
      const updatedQuestion = { ...selectedQuestion };
      updatedQuestion[type] = updatedQuestion[type].filter((_, i) => i !== index);
      setSelectedQuestion(updatedQuestion);
    }
  };

  const handleTestCaseChange = (
    type: "testcases" | "internalTestCases",
    index: number,
    field: "input" | "output" | "explanation",
    value: string
  ) => {
    if (selectedQuestion) {
      const updatedQuestion = { ...selectedQuestion };
      updatedQuestion[type][index][field] = value;
      setSelectedQuestion(updatedQuestion);
    }
  };

  const handleCreate = () => {
    router.push("/Programming_Questions/create");
  };

  // Pagination logic
  const startIndex = (currentPage - 1) * itemsPerPage;
  const visibleQuestions = questions.slice(startIndex, startIndex + itemsPerPage);

  const handlePageChange = (event: React.ChangeEvent<unknown>, page: number) => {
    setCurrentPage(page);
  };


  const handleDelete = async (id:string) => {
    try {
      const confirmed = window.confirm(
        "Are you sure you want to delete this question?"
      );
      if (!confirmed) return;
      setIsLoading(true);

      // Ensure questionId is available
      if (!id) {
        toast.error("No question ID available.");
        setIsLoading(false);
        return;
      }
  
      // Send the DELETE request with the question ID in the request body
      const response = await axios.delete("/api/Programming_Questions", {
        data: { id }, // Pass the id in the body
      });
  
      if (response.status === 200) {
        toast.success("Question deleted successfully!");
        if (fetchQuestions) fetchQuestions(); // Refresh the list if applicable
      } else {
        toast.error(response.data.error || "Failed to delete question.");
      }
    } catch (error) {
      console.error("Error deleting question:", error);
      toast.error("An error occurred while deleting the question.");
    }finally{
      setIsLoading(false);
    }
  };
  
  
  

  return (
    <div className="flex flex-col min-h-screen">
    <div className="container mx-auto p-4 sm:p-6 lg:p-10 relative">
          
          {isLoader && (
        <div className="absolute inset-0 z-50 pointer-events-none">
          {/* BorderBeam around the container */}
          <div className="relative h-full w-full">
            <BorderBeam />
          </div>
        </div>
      )}

      <ToastContainer/>
      <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold absolute top-4 sm:top-6 lg:top-8 mb-4 sm:mb-6 lg:mb-8">Programming Questions</h1>
      {/* Create Button */}
      <Button
        onClick={handleCreate}
        className="absolute top-4 sm:top-6 lg:top-8 right-4 sm:right-6 lg:right-8"
      >
        &#43; Add
      </Button>
      {/* Centered Loader Overlay */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-75 z-50">
          <Loader className="h-8 w-8 animate-spin" />
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-4 pt-16 sm:pt-20">
        {visibleQuestions.map((question) => (
          <div
            key={question.id}
            className="p-4 border rounded-md shadow flex justify-between items-center"
          >
            <div className="flex items-center">
              <div>
                <h3 className="font-semibold text-sm sm:text-base lg:text-lg">{question.title}</h3>
                {/* You can include additional information like difficulty here */}
              </div>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={() => openCard(question)}
                className="px-4 py-2 rounded flex items-center justify-center"
              >
                <Eye className="h-5 w-5 mr-2" />
              </button>
              <button onClick={() => handleDelete(question.id)}
                disabled={isLoading}>
                <Trash2 className='h-5 w-5 hover:text-red-600 '/>
              </button>
            </div>
          </div>
        ))}
      </div>



      {/* Pagination Component */}
      <div className="flex justify-center mt-6 mb-6 ">
        <Pagination
          count={Math.ceil(questions.length / itemsPerPage)}
          page={currentPage}
          onChange={handlePageChange}
          sx={{
            '& .MuiPaginationItem-root': {
              color: '#19105B',
            },
            '& .MuiPaginationItem-root.Mui-selected': {
              backgroundColor: '#19105B',
              color: 'white',
            },
          }}
          shape="rounded"
        />
      </div>

      {/* Question Details Modal */}
      <Dialog open={isCardVisible} onOpenChange={(open) => !open && closeCard()}>
        <DialogContent className="sm:max-w-[725px]">
          <DialogHeader>
            <DialogTitle>{isEditing ? "Edit Question" : "View Question"}</DialogTitle>
            <DialogDescription>
              {isEditing ? "Make changes to the question here. Click save when you're done." : "View the details of the selected question."}
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh] overflow-y-auto">
            <div className="space-y-4 p-4">
              {/* Title Field */}
              <div className="space-y-2">
                <Label htmlFor="title">
                  Title <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="title"
                  value={selectedQuestion?.title || ""}
                  onChange={(e) =>
                    setSelectedQuestion(prev => ({ ...prev!, title: e.target.value }))
                  }
                  disabled={!isEditing}
                  className={getBorderClass("title")}
                />
              </div>

              {/* Question Field */}
              <div className="space-y-2">
                <Label htmlFor="question">
                  Question <span className="text-red-500">*</span>
                </Label>
                <Textarea
                  id="question"
                  value={selectedQuestion?.question || ""}
                  onChange={(e) =>
                    setSelectedQuestion(prev => ({ ...prev!, question: e.target.value }))
                  }
                  disabled={!isEditing}
                  className={getBorderClass("question")}
                />
              </div>

              {/* Test Cases */}
              {["testcases", "internalTestCases"].map((type) => (
                <div key={type} className="space-y-2">
                  <Label className="capitalize">
                    {type.replace(/([A-Z])/g, " $1")} <span className="text-red-500">*</span>
                  </Label>
                  {(selectedQuestion?.[type as "testcases" | "internalTestCases"] || []).map(
                    (testcase: TestCase, index: number) => (
                      <div key={index} className="flex space-x-2 mb-2">
                        <Input
                          placeholder="Input"
                          value={testcase.input}
                          onChange={(e) =>
                            handleTestCaseChange(type as "testcases" | "internalTestCases", index, "input", e.target.value)
                          }
                          disabled={!isEditing}
                          className={`flex-1 ${getBorderClass(type as "testcases" | "internalTestCases")}`}
                        />
                        <Input
                          placeholder="Output"
                          value={testcase.output}
                          onChange={(e) =>
                            handleTestCaseChange(type as "testcases" | "internalTestCases", index, "output", e.target.value)
                          }
                          disabled={!isEditing}
                          className={`flex-1 ${getBorderClass(type as "testcases" | "internalTestCases")}`}
                        />
                        {type === "testcases" && (
                          <Input
                            placeholder="Explanation"
                            value={testcase.explanation}
                            onChange={(e) =>
                              handleTestCaseChange(type as "testcases" | "internalTestCases", index, "explanation", e.target.value)
                            }
                            disabled={!isEditing}
                            className={`flex-1 ${getBorderClass("testcases")}`}
                          />
                        )}
                        {isEditing && (
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => handleRemoveTestCase(type as "testcases" | "internalTestCases", index)}
                            className="flex-shrink-0 border-red-500"
                          >
                            &minus;
                          </Button>
                        )}
                      </div>
                    )
                  )}
                  {isEditing && (
                    <Button
                      variant="outline"
                      onClick={() => handleAddTestCase(type as "testcases" | "internalTestCases")}
                      className="mt-2 border-indigo-900"
                    >
                      Add {type === "testcases" ? "Test Case" : "Internal Test Case"}
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </ScrollArea>
          <DialogFooter>
            {isEditing ? (
              <>
                <Button variant="outline" onClick={() => setIsEditing(false)} disabled={isLoading}>
                  Cancel
                </Button>
                <Button onClick={handleSave} disabled={isLoading}>
                  {isLoading ? (
                    <>
                      <Loader className="mr-2 h-4 w-4 animate-spin" color="text-white" />
                      Saving
                    </>
                  ) : (
                    'Save changes'
                  )}
                </Button>
              </> 
            ) : (
              <Button onClick={handleEdit}>Edit</Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

    
      </div>
      {/* Footer */}
  <footer className="bg-gray-200 py-2 px-2 mt-auto">
    <div className="flex justify-between items-center">
      <p className="text-sm text-gray-600 m-0">
        © 2024 JMAN, All Rights Reserved
      </p>
      <Image
        src={FooterImage}
        alt="JMAN Logo"
        width={120}
        height={40}
        className="m-0"
      />
    </div>
  </footer>
</div>
  );
}


