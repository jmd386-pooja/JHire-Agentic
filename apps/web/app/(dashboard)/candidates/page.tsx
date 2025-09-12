"use client";

import ResumeForm from "@/components/layout/ResumeForm";
import CandidatesTable from "@/components/layout/CandidatesTable";

export default function CandidatesPage() {
  return (
    <div className="flex flex-col">
      <div className="space-y-6 p-8 pt-3 relative max-w-7xl mx-auto w-full">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-3xl font-bold px-4 pt-4">Candidates</h2>
          <div>
            <ResumeForm />
          </div>
        </div>

        <div>
          <CandidatesTable />
        </div>
      </div>      
    </div>
  );
}
