"use client";

import { useForm, useFieldArray } from "react-hook-form";
import { useState } from "react";
import axios from "axios";
import { useRouter } from "next/navigation";
import {toast,ToastContainer} from "react-toastify"
import Image from "next/image";
import JmanLogo from "@/images/JMANLogoBlue.png"
// Define a type for the form structure
type TestCase = {
  input: string;
  output: string;
  explanation?: string; // Added explanation field
};

type QuestionFormData = {
  id: string;
  title: string; // Added title field
  question: string;
  testcases: TestCase[];
  internalTestCases: TestCase[];
  createdAt: string;
  constraints: string[];
  // difficulty: "Easy" | "Medium" | "Hard";
};

export default function QuestionFormPage() {
  const { register, handleSubmit, control, reset, setValue, watch } = useForm<QuestionFormData>({
    defaultValues: {
      id: "",
      title: "",
      question: "",
      testcases: [],
      internalTestCases: [],
      createdAt: new Date().toISOString(),
      constraints: [],
      // difficulty: "Easy",
    },
  });

  const router= useRouter();

  const { fields: testCasesFields, append: addTestCase, remove: removeTestCase } = useFieldArray({
    control,
    name: "testcases", // Must match the property in `QuestionFormData`
  });

  const {
    fields: internalTestCasesFields,
    append: addInternalTestCase,
    remove: removeInternalTestCase,
  } = useFieldArray({
    control,
    name: "internalTestCases", // Must match the property in `QuestionFormData`
  });

  const constraints = watch("constraints");

  const addConstraint = () => {
    setValue("constraints", [...constraints, ""]);
  };

  const removeConstraint = (index: number) => {
    setValue(
      "constraints",
      constraints.filter((_, i) => i !== index)
    );
  };

  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (data: QuestionFormData) => {
    setSubmitting(true);
    try {
      const payload = {
        ...data,
        id: crypto.randomUUID(),
        createdAt: new Date().toISOString(),
        testcases: data.testcases.map((testCase) => ({
          input: testCase.input,
          output: testCase.output,
          explanation: testCase.explanation, // Added explanation
        })),
        internalTestCases: data.internalTestCases.map((testCase) => ({
          input: testCase.input,
          output: testCase.output,
          // Removed explanation for internalTestCases
        })),
      };
  
      console.log("Submitting payload:", payload);
  
      const response = await axios.post("/api/Programming_Questions", payload);
  
      if (response.status === 201) {
        toast.success("Question created successfully!", { autoClose: 2000 }); // Toast message for success
        setTimeout(()=>{
          router.push("/Programming_Questions");
        },2000);
        }
    } catch (error) {
      console.error("Error creating question:", error);
      toast.error("Failed to create the question.", { autoClose: 2000 }); // Toast message for error
    } finally {
      setSubmitting(false);
    }
  };
  
  const handleBack=()=>{
    router.push("/Programming_Questions")
  }

//   return (
    
// <div className="max-w-4xl mx-auto p-4 sm:p-6 md:p-8 lg:p-12 relative min-h-screen flex flex-col">
//   <ToastContainer />
//   <h1 className="text-xl sm:text-2xl font-bold mb-6">Create Programming Question</h1>

//   {/* Create Button */}
//   <button
//     onClick={handleBack}
//     style={{ backgroundColor: '#19105B', color: 'white' }}
//     className="absolute top-4 sm:top-6 md:top-8 right-4 sm:right-6 md:right-8 px-3 sm:px-4 py-2 rounded flex items-center text-sm sm:text-base"
//   >
//     <svg
//       xmlns="http://www.w3.org/2000/svg"
//       width="16"
//       height="16"
//       fill="currentColor"
//       className="mr-2"
//       viewBox="0 0 16 16"
//     >
//       <path d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z" />
//     </svg>
//     Back
//   </button>

  // <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
  //   {/* Title */}
  //   <div>
  //     <label className="block text-sm font-medium mb-1" htmlFor="title">
  //       Title <span className="text-red-500">*</span>
  //     </label>
  //     <input
  //       {...register('title', { required: true })}
  //       id="title"
  //       type="text"
  //       className="w-full border rounded px-3 py-2"
  //       placeholder="Enter the title of the question"
  //     />
  //   </div>

  //   {/* Question */}
  //   <div>
  //     <label className="block text-sm font-medium mb-1" htmlFor="question">
  //       Question <span className="text-red-500">*</span>
  //     </label>
  //     <textarea
  //       {...register('question', { required: true })}
  //       id="question"
  //       rows={4}
  //       className="w-full border rounded px-3 py-2"
  //       placeholder="Enter the programming question"
  //     ></textarea>
  //   </div>

  //   {/* Test Cases */}
  //   <div>
  //     <label className="block text-sm font-medium mb-2">
  //       Test Cases <span className="text-red-500">*</span>
  //     </label>
  //     {testCasesFields.map((field, index) => (
  //       <div
  //         key={field.id}
  //         className="flex flex-wrap sm:flex-nowrap items-center space-y-2 sm:space-y-0 sm:space-x-2 mb-3"
  //       >
  //         <input
  //           {...register(`testcases.${index}.input`, { required: true })}
  //           placeholder="Input"
  //           className="w-full sm:w-1/4 border rounded px-3 py-2"
  //         />
  //         <input
  //           {...register(`testcases.${index}.output`, { required: true })}
  //           placeholder="Output"
  //           className="w-full sm:w-1/4 border rounded px-3 py-2"
  //         />
  //         <input
  //           {...register(`testcases.${index}.explanation`, { required: true })}
  //           placeholder="Explanation"
  //           className="w-full sm:w-1/4 border rounded px-3 py-2"
  //         />
  //         <div className="flex space-x-2 mt-2 sm:mt-0">
  //           <button
  //             type="button"
  //             onClick={() => removeTestCase(index)}
  //             className="text-red-500 text-xl sm:text-2xl px-2"
  //           >
  //             &minus;
  //           </button>
  //           <button
  //             type="button"
  //             onClick={() => addTestCase({ input: '', output: '', explanation: '' })}
  //             className="text-violet-900 text-xl sm:text-2xl px-2"
  //           >
  //             &#43;
  //           </button>
  //         </div>
  //       </div>
  //     ))}
  //     {testCasesFields.length === 0 && (
  //       <button
  //         type="button"
  //         onClick={() => addTestCase({ input: '', output: '', explanation: '' })}
  //         className="text-violet-900 text-2xl px-2"
  //       >
  //         &#43;
  //       </button>
  //     )}
  //   </div>

  //   {/* Internal Test Cases */}
  //   <div>
  //     <label className="block text-sm font-medium mb-2">
  //       Internal Test Cases <span className="text-red-500">*</span>
  //     </label>
  //     {internalTestCasesFields.map((field, index) => (
  //       <div
  //         key={field.id}
  //         className="flex flex-wrap sm:flex-nowrap items-center space-y-2 sm:space-y-0 sm:space-x-2 mb-3"
  //       >
  //         <input
  //           {...register(`internalTestCases.${index}.input`, { required: true })}
  //           placeholder="Input"
  //           className="w-full sm:w-1/4 border rounded px-3 py-2"
  //         />
  //         <input
  //           {...register(`internalTestCases.${index}.output`, { required: true })}
  //           placeholder="Output"
  //           className="w-full sm:w-1/4 border rounded px-3 py-2"
  //         />
  //         <div className="flex space-x-2 mt-2 sm:mt-0">
  //           <button
  //             type="button"
  //             onClick={() => removeInternalTestCase(index)}
  //             className="text-red-500 text-xl sm:text-2xl px-2"
  //           >
  //             &minus;
  //           </button>
  //           <button
  //             type="button"
  //             onClick={() => addInternalTestCase({ input: '', output: '' })}
  //             className="text-violet-900 text-xl sm:text-2xl px-2"
  //           >
  //             &#43;
  //           </button>
  //         </div>
  //       </div>
  //     ))}
  //     {internalTestCasesFields.length === 0 && (
  //       <button
  //         type="button"
  //         onClick={() => addInternalTestCase({ input: '', output: '' })}
  //         className="text-violet-900 text-2xl px-2"
  //       >
  //         &#43;
  //       </button>
  //     )}
  //   </div>

  //   {/* Constraints */}
  //   <div>
  //     <label className="block text-sm font-medium mb-2">
  //       Constraints <span className="text-red-500">*</span>
  //     </label>
  //     {constraints.map((constraint, index) => (
  //       <div
  //         key={index}
  //         className="flex flex-wrap sm:flex-nowrap items-center space-y-2 sm:space-y-0 sm:space-x-2 mb-3"
  //       >
  //         <input
  //           {...register(`constraints.${index}`, { required: true })}
  //           value={constraint}
  //           onChange={(e) => {
  //             const updatedConstraints = [...constraints];
  //             updatedConstraints[index] = e.target.value;
  //             setValue('constraints', updatedConstraints);
  //           }}
  //           placeholder="Constraint"
  //           className="w-full border rounded px-3 py-2"
  //         />
  //         <div className="flex space-x-2 mt-2 sm:mt-0">
  //           <button
  //             type="button"
  //             onClick={() => removeConstraint(index)}
  //             className="text-red-500 text-xl sm:text-2xl px-2"
  //           >
  //             &minus;
  //           </button>
  //           <button
  //             type="button"
  //             onClick={addConstraint}
  //             className="text-violet-900 text-xl sm:text-2xl px-2"
  //           >
  //             &#43;
  //           </button>
  //         </div>
  //       </div>
  //     ))}
  //     {constraints.length === 0 && (
  //       <button
  //         type="button"
  //         onClick={addConstraint}
  //         className="text-violet-900 text-2xl px-2"
  //       >
  //         &#43;
  //       </button>
  //     )}
  //   </div>

  //   {/* Submit Button */}
  //   <div>
  //     <button
  //       type="submit"
  //       style={{ backgroundColor: '#19105B', color: 'white' }}
  //       className="w-full sm:w-auto px-4 py-2 rounded"
  //       disabled={submitting}
  //     >
  //       {submitting ? 'Saving...' : 'Save'}
  //     </button>
  //   </div>
  // </form>
//   {/* Footer */}
//   <div className="w-full bg-gray-200 py-2 px-2 mt-auto">
//       <div className="max-w-4xl mx-auto flex justify-between items-center">
//         <p className="text-sm text-gray-600 m-0">© 2024 JMAN, All Rights Reserved</p>
//         <Image
//           src={JmanLogo}
//           alt="JMAN Logo"
//           width={120}
//           height={40}
//           className="m-0"
//         />
//       </div>
//     </div>
//   </div>
//   );
// }

return (
  <div className="min-h-screen flex flex-col">
    {/* Main Content */}
    <div className="flex-1 max-w-4xl mx-auto p-4 sm:p-6 md:p-8 lg:p-12 relative w-full">
      <ToastContainer />
      <h1 className="text-xl sm:text-2xl font-bold mb-6">Create Programming Question</h1>

      {/* Create Button */}
      <button
        onClick={handleBack}
        style={{ backgroundColor: '#19105B', color: 'white' }}
        className="absolute top-4 sm:top-6 md:top-8 right-4 sm:right-6 md:right-8 px-3 sm:px-4 py-2 rounded flex items-center text-sm sm:text-base"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          fill="currentColor"
          className="mr-2"
          viewBox="0 0 16 16"
        >
          <path d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z" />
        </svg>
        Back
      </button>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
    {/* Title */}
    <div>
      <label className="block text-sm font-medium mb-1" htmlFor="title">
        Title <span className="text-red-500">*</span>
      </label>
      <input
        {...register('title', { required: true })}
        id="title"
        type="text"
        className="w-full border rounded px-3 py-2"
        placeholder="Enter the title of the question"
      />
    </div>

    {/* Question */}
    <div>
      <label className="block text-sm font-medium mb-1" htmlFor="question">
        Question <span className="text-red-500">*</span>
      </label>
      <textarea
        {...register('question', { required: true })}
        id="question"
        rows={4}
        className="w-full border rounded px-3 py-2"
        placeholder="Enter the programming question"
      ></textarea>
    </div>

    {/* Test Cases */}
    <div>
      <label className="block text-sm font-medium mb-2">
        Test Cases <span className="text-red-500">*</span>
      </label>
      {testCasesFields.map((field, index) => (
        <div
          key={field.id}
          className="flex flex-wrap sm:flex-nowrap items-center space-y-2 sm:space-y-0 sm:space-x-2 mb-3"
        >
          <input
            {...register(`testcases.${index}.input`, { required: true })}
            placeholder="Input"
            className="w-full sm:w-1/4 border rounded px-3 py-2"
          />
          <input
            {...register(`testcases.${index}.output`, { required: true })}
            placeholder="Output"
            className="w-full sm:w-1/4 border rounded px-3 py-2"
          />
          <input
            {...register(`testcases.${index}.explanation`, { required: true })}
            placeholder="Explanation"
            className="w-full sm:w-1/4 border rounded px-3 py-2"
          />
          <div className="flex space-x-2 mt-2 sm:mt-0">
            <button
              type="button"
              onClick={() => removeTestCase(index)}
              className="text-red-500 text-xl sm:text-2xl px-2"
            >
              &minus;
            </button>
            <button
              type="button"
              onClick={() => addTestCase({ input: '', output: '', explanation: '' })}
              className="text-violet-900 text-xl sm:text-2xl px-2"
            >
              &#43;
            </button>
          </div>
        </div>
      ))}
      {testCasesFields.length === 0 && (
        <button
          type="button"
          onClick={() => addTestCase({ input: '', output: '', explanation: '' })}
          className="text-violet-900 text-2xl px-2"
        >
          &#43;
        </button>
      )}
    </div>

    {/* Internal Test Cases */}
    <div>
      <label className="block text-sm font-medium mb-2">
        Internal Test Cases <span className="text-red-500">*</span>
      </label>
      {internalTestCasesFields.map((field, index) => (
        <div
          key={field.id}
          className="flex flex-wrap sm:flex-nowrap items-center space-y-2 sm:space-y-0 sm:space-x-2 mb-3"
        >
          <input
            {...register(`internalTestCases.${index}.input`, { required: true })}
            placeholder="Input"
            className="w-full sm:w-1/4 border rounded px-3 py-2"
          />
          <input
            {...register(`internalTestCases.${index}.output`, { required: true })}
            placeholder="Output"
            className="w-full sm:w-1/4 border rounded px-3 py-2"
          />
          <div className="flex space-x-2 mt-2 sm:mt-0">
            <button
              type="button"
              onClick={() => removeInternalTestCase(index)}
              className="text-red-500 text-xl sm:text-2xl px-2"
            >
              &minus;
            </button>
            <button
              type="button"
              onClick={() => addInternalTestCase({ input: '', output: '' })}
              className="text-violet-900 text-xl sm:text-2xl px-2"
            >
              &#43;
            </button>
          </div>
        </div>
      ))}
      {internalTestCasesFields.length === 0 && (
        <button
          type="button"
          onClick={() => addInternalTestCase({ input: '', output: '' })}
          className="text-violet-900 text-2xl px-2"
        >
          &#43;
        </button>
      )}
    </div>

    {/* Constraints */}
    <div>
      <label className="block text-sm font-medium mb-2">
        Constraints <span className="text-red-500">*</span>
      </label>
      {constraints.map((constraint, index) => (
        <div
          key={index}
          className="flex flex-wrap sm:flex-nowrap items-center space-y-2 sm:space-y-0 sm:space-x-2 mb-3"
        >
          <input
            {...register(`constraints.${index}`, { required: true })}
            value={constraint}
            onChange={(e) => {
              const updatedConstraints = [...constraints];
              updatedConstraints[index] = e.target.value;
              setValue('constraints', updatedConstraints);
            }}
            placeholder="Constraint"
            className="w-full border rounded px-3 py-2"
          />
          <div className="flex space-x-2 mt-2 sm:mt-0">
            <button
              type="button"
              onClick={() => removeConstraint(index)}
              className="text-red-500 text-xl sm:text-2xl px-2"
            >
              &minus;
            </button>
            <button
              type="button"
              onClick={addConstraint}
              className="text-violet-900 text-xl sm:text-2xl px-2"
            >
              &#43;
            </button>
          </div>
        </div>
      ))}
      {constraints.length === 0 && (
        <button
          type="button"
          onClick={addConstraint}
          className="text-violet-900 text-2xl px-2"
        >
          &#43;
        </button>
      )}
    </div>

    {/* Submit Button */}
    <div>
      <button
        type="submit"
        style={{ backgroundColor: '#19105B', color: 'white' }}
        className="w-full sm:w-auto px-4 py-2 rounded"
        disabled={submitting}
      >
        {submitting ? 'Saving...' : 'Save'}
      </button>
    </div>
  </form>
    </div>

    {/* Footer */}
    <footer className="w-full bg-gray-200 py-2 px-2 mt-auto">
      <div className="max-w-4xl mx-auto flex justify-between items-center">
        <p className="text-sm text-gray-600 m-0">© 2024 JMAN, All Rights Reserved</p>
        <Image
          src={JmanLogo}
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
