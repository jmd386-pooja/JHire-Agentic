"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Eye,
  Mail,
  Search,
  Calendar,
  LampDesk,
  Parentheses,
  Award,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Checkbox } from "@/components/ui/checkbox";
import { useTheme } from "next-themes";
import { format } from "date-fns";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Loader } from "@/components/ui/loader";
import { Card, CardContent } from "@/components/ui/card";
import { BorderBeam } from "../ui/border-beam";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import { AnimatePresence, motion, useInView } from "framer-motion";

interface Candidate {
  id: string;
  name: string;
  email: string;
  ph_number: string | null;
  status: string;
  temp_name: string;
  tempPassword: string;
  Exam_URL: string;
  College: string | null;
  Exam_date: string;
  Expiry: string | null;
  interviewStatus: string;
  interviewDetails?: {
    Interviewscore: number;
    Codingscore: number;
  };
}

/** In-view animated wrapper for cards/sections */
const InViewCard: React.FC<React.PropsWithChildren<{ className?: string }>> = ({
  className,
  children,
}) => {
  const ref = useRef<HTMLDivElement | null>(null);
  const inView = useInView(ref, { amount: 0.25, margin: "0px 0px -10% 0px" });

  return (
    <motion.div
      ref={ref}
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={
        inView
          ? { opacity: 1, y: 0, pointerEvents: "auto" }
          : { opacity: 0, y: 10, pointerEvents: "none" }
      }
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
};

const CandidatesTable: React.FC = () => {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(
    null
  );
  const [isEditing, setIsEditing] = useState(false);
  const [editedCandidate, setEditedCandidate] = useState<Candidate | null>(
    null
  );
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>(
    []
  );
  const [selectAll, setSelectAll] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoader, setIsLoader] = useState(false);
  const { toast } = useToast();
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [collegeList, setCollegeList] = useState<string[]>([]);
  const [selectedCollege, setSelectedCollege] = useState<string>("");
  const [examDateTime, setExamDateTime] = useState<string>("");

  const convertUTCToLocal = (utcDate: string | null): string => {
    if (!utcDate) return "";
    const date = new Date(utcDate);
    date.setMinutes(date.getMinutes() - (5 * 60 + 30));
    const localYear = date.getFullYear();
    const localMonth = String(date.getMonth() + 1).padStart(2, "0");
    const localDate = String(date.getDate()).padStart(2, "0");
    const localHours = String(date.getHours()).padStart(2, "0");
    const localMinutes = String(date.getMinutes()).padStart(2, "0");
    return `${localYear}-${localMonth}-${localDate}T${localHours}:${localMinutes}`;
  };

  const fetchCandidates = useCallback(async () => {
    setIsLoader(true);
    try {
      const response = await fetch("/api/candidates/bulk");
      if (!response.ok) throw new Error("Failed to fetch candidates.");
      const candidatesData = await response.json();

      const interviewResponse = await fetch("/api/interviews");
      if (!interviewResponse.ok)
        throw new Error("Failed to fetch interview data.");
      const interviewData = await interviewResponse.json();

      const candidatesWithScores = candidatesData.data.map(
        (candidate: Candidate) => {
          const interview = interviewData.find(
            (interview: any) =>
              interview.candidate_id === parseInt(candidate.id)
          );
          const interviewScore = interview ? interview.Interviewscore : null;
          const Codingscore = interview ? interview.Codingscore : null;
          const interviewStatus =
            interviewScore !== null && Codingscore !== null
              ? (interviewScore + Codingscore) / 2 >= 80
                ? "SELECTED"
                : "NOT SELECTED"
              : "N/A";

          return {
            ...candidate,
            Exam_date: candidate.Exam_date
              ? convertUTCToLocal(candidate.Exam_date)
              : "",
            Expiry: candidate.Expiry
              ? convertUTCToLocal(candidate.Expiry)
              : "",
            interviewDetails: interview || {},
            interviewStatus,
          };
        }
      );

      setCandidates(candidatesWithScores);

      const hardcodedColleges = ["CIT", "SVCE", "GEU"];
      setCollegeList(hardcodedColleges);
    } catch (error) {
      console.error("Error fetching candidates:", error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to fetch candidates",
      });
    } finally {
      setIsLoader(false);
    }
  }, [toast]);

  const sendInvitation = async (
    candidateId: string,
    candidatename: string,
    candidateEmail: string,
    candidateExam_URL: string,
    candidatetemp_name: string,
    candidatetempPassword: string,
    ExamDate: string
  ) => {
    const formattedExamDate = new Date(ExamDate).toLocaleString("en-US", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
    setLoadingId(candidateId);
    try {
      const response = await fetch("/api/send-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: candidateId,
          to: candidateEmail,
          subject: "Interview Invitation - JMAN",
          htmlContent: `
          <p>Dear ${candidatename},</p>
          <p>Greetings from JMAN Group!</p>
          <p>We would like to block your calendar for the <strong>Level 1 Technical Interview</strong>. Kindly ensure your availability for the session. Please find your interview details below:</p>
          <h4>Interview Details</h4>
          <div style="margin-left: 20px;">
            <p><strong>Date and Time:</strong>${formattedExamDate}</p>
            <p><strong>Position:</strong> Software Engineer</p>
          </div>
          <h4>Login Credentials</h4>
          <div style="margin-left: 20px;">
            <p><strong>Username:</strong> <span style="font-weight: bold; color: #2a6cb5;">${candidateEmail}</span></p>
            <p><strong>Password:</strong> <span style="font-weight: bold; color: #2a6cb5;">${candidatetempPassword}</span></p>
          </div>
          <p>Use the link below to log in and access your interview details:</p>
          <p><a href="${candidateExam_URL}" style="color: #2a6cb5; text-decoration: underline;">Interview Link</a></p>
          <p>We kindly request you to confirm your attendance by selecting one of the options below:</p>
          <div style="margin: 20px 0;">
            <a href="${window.location.origin}/${candidateId}/accept"
              style="color: #4CAF50; font-weight: bold; text-decoration: none; font-size: 16px; margin-right: 30px; display: inline-block;">
              ✔ Accept Invitation
            </a>
            <a href="${window.location.origin}/${candidateId}/decline"
              style="color: #F44336; font-weight: bold; text-decoration: none; font-size: 16px; display: inline-block;">
              ✖ Decline Invitation
            </a>
          </div>
          <p>To ensure a smooth interview experience, please follow these guidelines:</p>
          <ul style="margin-left: 20px;">
            <li>Join at least five minutes prior to the scheduled time.</li>
            <li>Make sure you have stable internet connectivity, at least 5mbps.</li>
            <li>Check your microphone and camera settings before the start of the interview.</li>
            <li>Join the interview using a laptop/desktop only.</li>
            <li>Please join the link via web if you do not have Microsoft Teams installed.</li>
          </ul>
          <p>If you have any questions or need assistance, feel free to reach out to us.</p>
          <p>Regards,</p>
          <p>JMAN Group</p>`,
        }),
      });
      fetchCandidates();
      if (!response.ok) throw new Error("Failed to send invitation");

      toast({
        title: "Success",
        description: `Invitation sent successfully to candidate`,
      });
    } catch (error) {
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to send invitation",
      });
    } finally {
      setLoadingId(null);
    }
  };

  const sendBulkInvitations = async () => {
    if (isLoading) return;
    setIsLoading(true);
    try {
      const response = await fetch(`/api/send-bulk-email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidateIds: selectedCandidateIds }),
      });
      if (!response.ok) throw new Error("Failed to send bulk invitations");

      toast({
        title: "Success",
        description: "Invitations sent successfully to selected candidates",
      });

      setSelectedCandidateIds([]);
      setSelectAll(false);
      fetchCandidates();
    } catch (error) {
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to send bulk invitations",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const filteredCandidates = candidates.filter((candidate) => {
    const matchesSearchQuery = [
      candidate.name,
      candidate.status,
      candidate.College,
    ].some((field) => field?.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesSelectedDateTime = examDateTime
      ? candidate.Exam_date === examDateTime
      : true;
    const matchesCollege = selectedCollege
      ? candidate.College === selectedCollege
      : true;

    return matchesSearchQuery && matchesSelectedDateTime && matchesCollege;
  });

  const sortedCandidates = filteredCandidates.sort((a, b) => {
    const da = a.Exam_date ? new Date(a.Exam_date).getTime() : 0;
    const db = b.Exam_date ? new Date(b.Exam_date).getTime() : 0;
    return da - db;
  });

  const indexOfLastCandidate = currentPage * itemsPerPage;
  const indexOfFirstCandidate = indexOfLastCandidate - itemsPerPage;
  const currentCandidates = sortedCandidates.slice(
    indexOfFirstCandidate,
    indexOfLastCandidate
  );

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    setCurrentPage(1);
  };

  const handleView = (candidate: Candidate) => {
    setSelectedCandidate(candidate);
    setIsEditing(false);
  };

  const handleCollegeFilter = (college: string) => {
    setSelectedCollege(college);
    setCurrentPage(1);
  };

  const handleEdit = () => {
    setIsEditing(true);
    setEditedCandidate({ ...selectedCandidate } as Candidate);
  };

  const handleSave = async () => {
    if (!editedCandidate) return;

    try {
      setIsLoading(true);
      if (editedCandidate.Exam_date) {
        editedCandidate.Exam_date = convertUTCToLocal(
          editedCandidate.Exam_date
        );
      }
      if (editedCandidate.Expiry) {
        editedCandidate.Expiry = convertUTCToLocal(editedCandidate.Expiry);
      }
      const updatedCandidate = { ...editedCandidate, status: "PENDING" };

      const response = await fetch(`/api/candidates/bulk`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updatedCandidate),
      });

      if (!response.ok) throw new Error("Failed to update candidate.");

      setCandidates((prev) =>
        prev.map((c) => (c.id === editedCandidate.id ? editedCandidate : c))
      );
      setSelectedCandidate(null);
      setEditedCandidate(null);
      setIsEditing(false);

      toast({
        title: "Success",
        description: `Successfully Edited for Candidate`,
      });
    } catch (error) {
      console.error("Error saving candidate:", error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to save",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const fetchRef = useRef(fetchCandidates);

  useEffect(() => {
    fetchCandidates();
  }, [fetchCandidates]);

  useEffect(() => {
    fetchRef.current();
  }, []);

  useEffect(() => {
    fetchRef.current = fetchCandidates;
  }, [fetchCandidates]);

  useEffect(() => {
    const handler = () => fetchRef.current();
    window.addEventListener("candidates:refresh", handler);
    return () => window.removeEventListener("candidates:refresh", handler);
  }, []);

  const [selectedCandidate_exam, setSelectedCandidate_exam] =
    useState<Candidate | null>(null);
  const handleInterviewDetailsClick = (candidate: any) => {
    setSelectedCandidate_exam(candidate);
  };

  const handleModalClose = () => {
    setSelectedCandidate_exam(null);
    setSelectedCandidate(null);
    setEditedCandidate(null);
    setIsEditing(false);
  };

  const toggleCandidateSelection = (id: string) => {
    setSelectedCandidateIds((prev) =>
      prev.includes(id)
        ? prev.filter((candidateId) => candidateId !== id)
        : [...prev, id]
    );
  };

  const handleSelectAll = () => {
    if (selectAll) {
      setSelectedCandidateIds([]);
    } else {
      const pendingCandidates = candidates
        .filter((candidate) => candidate.status.toLowerCase() === "pending")
        .map((candidate) => candidate.id);

      setSelectedCandidateIds(pendingCandidates);
    }
    setSelectAll(!selectAll);
  };

  const handlePagination = (direction: string) => {
    if (
      direction === "next" &&
      currentPage < Math.ceil(filteredCandidates.length / itemsPerPage)
    ) {
      setCurrentPage(currentPage + 1);
    } else if (direction === "prev" && currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };

  const handleItemsPerPageChange = (
    e: React.ChangeEvent<HTMLSelectElement>
  ) => {
    setItemsPerPage(Number(e.target.value));
    setCurrentPage(1);
  };

  return (
    <motion.div
      className="container mx-auto px-4 py-4"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
    >
      {isLoader && (
        <div className="absolute inset-0 z-50 pointer-events-none">
          <div className="relative h-full w-full">
            <BorderBeam />
          </div>
        </div>
      )}

      <InViewCard>
        <Card className="mb-8 bg-transparent">
          <CardContent className="p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center space-x-2">
                <Checkbox
                  checked={selectAll}
                  onCheckedChange={handleSelectAll}
                  id="select-all"
                />
                <Button
                  onClick={sendBulkInvitations}
                  disabled={selectedCandidateIds.length === 0}
                  className="flex items-center"
                >
                  {isLoading ? (
                    <>
                      <Loader size="sm" className="mr-2" color="text-white" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Mail className="h-4 w-4 mr-2" />
                      Send Bulk Invitations
                    </>
                  )}
                </Button>
              </div>

              <div className="flex items-center space-x-2 px-2">
                <Input
                  type="datetime-local"
                  value={examDateTime}
                  onChange={(e) => setExamDateTime(e.target.value)}
                  required
                  className="w-full"
                />
              </div>

              <div className="flex items-center space-x-2">
                <Label htmlFor="college-filter" className="text-gray-500">
                  College:
                </Label>
                <select
                  id="college-filter"
                  value={selectedCollege}
                  onChange={(e) => handleCollegeFilter(e.target.value)}
                  className="w-28 border rounded-md p-1"
                >
                  <option value="">All Colleges</option>
                  {collegeList.map((college) => (
                    <option key={college} value={college}>
                      {college}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center space-x-2">
                <Search className="h-4 w-4 text-gray-500" />
                <Input
                  type="text"
                  placeholder="Search candidates..."
                  value={searchQuery}
                  onChange={(e) => handleSearch(e.target.value)}
                  className="w-32"
                />
              </div>
            </div>
          </CardContent>
        </Card>
      </InViewCard>

      <div className="grid gap-4">
        <AnimatePresence initial={false} mode="popLayout">
          {currentCandidates.map((candidate) => (
            <InViewCard key={candidate.id}>
              <motion.div layout>
                <Card>
                  <CardContent className="p-6 flex justify-between items-center">
                    <div className="flex items-center space-x-4">
                      <Checkbox
                        checked={selectedCandidateIds.includes(candidate.id)}
                        onCheckedChange={() =>
                          toggleCandidateSelection(candidate.id)
                        }
                      />
                      <div>
                        <h3 className="font-semibold">{candidate.name}</h3>
                        <p className="text-sm text-gray-600">
                          {candidate.email}
                        </p>
                        <p className="text-xs text-gray-500">
                          Interview Date:{" "}
                          {candidate.Exam_date
                            ? new Date(candidate.Exam_date).toLocaleDateString()
                            : "-"}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                      <span
                        className={`px-2 py-1 rounded-full text-xs ${
                          candidate.status === "PENDING"
                            ? "bg-yellow-100 text-yellow-800"
                            : candidate.status === "INVITED"
                            ? "bg-green-100 text-green-800"
                            : candidate.status === "ACCEPTED"
                            ? "bg-blue-100 text-blue-800"
                            : candidate.status === "DECLINED"
                            ? "bg-red-100 text-red-800"
                            : ""
                        }`}
                      >
                        {candidate.status.toUpperCase()}
                      </span>

                      <HoverCard>
                        <HoverCardTrigger>
                          <span
                            className={`w-32 px-3 py-1 text-center inline-block rounded-full text-xs font-medium transition-all duration-500 ease-in-out transform 
                              ${
                                candidate.interviewStatus === "SELECTED"
                                  ? "bg-green-100 text-green-800 shadow-green-400 hover:shadow-lg hover:scale-105"
                                  : candidate.interviewStatus === "NOT SELECTED"
                                  ? "bg-red-100 text-red-800 shadow-red-400 hover:shadow-lg hover:scale-105"
                                  : "bg-gray-100 text-gray-800 shadow-gray-400 hover:shadow-lg hover:scale-105"
                              }
                              shadow-sm`}
                          >
                            {candidate.interviewStatus}
                          </span>
                        </HoverCardTrigger>
                        <HoverCardContent>
                          <div className="text-center border-b pb-2">
                            <h3 className="text-lg font-semibold text-gray-800">
                              Interview Details
                            </h3>
                          </div>

                          <div className="space-y-3 mt-2">
                            <div className="flex items-center space-x-2">
                              <LampDesk className="h-4 w-4" />
                              <p>
                                <strong className="text-gray-600">
                                  Interview Score:
                                </strong>{" "}
                                <span className="font-medium text-blue-600">
                                  {candidate.interviewDetails?.Interviewscore ??
                                    "N/A"}
                                </span>
                              </p>
                            </div>

                            <div className="flex items-center space-x-2">
                              <Parentheses className="h-4 w-4" />
                              <p>
                                <strong className="text-gray-600">
                                  Coding Score:
                                </strong>{" "}
                                <span className="font-medium text-green-600">
                                  {candidate.interviewDetails?.Codingscore ??
                                    "N/A"}
                                </span>
                              </p>
                            </div>

                            <div className="flex items-center space-x-2">
                              <Award className="h-4 w-4" />
                              <p>
                                <strong className="text-gray-600">
                                  Status:
                                </strong>{" "}
                                <span
                                  className={`font-medium ${
                                    candidate.interviewStatus === "SELECTED"
                                      ? "text-green-600"
                                      : candidate.interviewStatus ===
                                        "NOT SELECTED"
                                      ? "text-red-600"
                                      : "text-gray-600"
                                  }`}
                                >
                                  {candidate.interviewStatus}
                                </span>
                              </p>
                            </div>
                          </div>
                        </HoverCardContent>
                      </HoverCard>

                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleView(candidate)}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          sendInvitation(
                            candidate.id,
                            candidate.name,
                            candidate.email.toString(),
                            candidate.Exam_URL,
                            candidate.temp_name,
                            candidate.tempPassword,
                            candidate.Exam_date
                          )
                        }
                        disabled={
                          loadingId === candidate.id ||
                          candidate.status !== "PENDING"
                        }
                      >
                        {loadingId === candidate.id ? (
                          <Loader size="sm" />
                        ) : (
                          <Mail className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            </InViewCard>
          ))}
        </AnimatePresence>
      </div>

      <InViewCard>
        <div className="mt-6 flex items-center justify-between">
          <Button
            onClick={() => handlePagination("prev")}
            disabled={currentPage === 1}
          >
            Previous
          </Button>
          <span>{`Page ${currentPage} of ${Math.ceil(
            filteredCandidates.length / itemsPerPage
          )}`}</span>
          <div className="flex items-center space-x-2">
            <Label htmlFor="items-per-page">Items per page:</Label>
            <select
              id="items-per-page"
              value={itemsPerPage}
              onChange={handleItemsPerPageChange}
              className="border rounded p-1"
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </div>
          <Button
            onClick={() => handlePagination("next")}
            disabled={
              currentPage ===
              Math.ceil(filteredCandidates.length / itemsPerPage)
            }
          >
            Next
          </Button>
        </div>
      </InViewCard>

      {selectedCandidate && (
        <Dialog open={true} onOpenChange={handleModalClose}>
          <DialogContent className="sm:max-w-[425px]">
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.6 }}
            >
              <DialogHeader>
                <DialogTitle>Candidate Details</DialogTitle>
                <DialogDescription>
                  View and edit candidate information.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                {[
                  { key: "name", label: "Name" },
                  { key: "email", label: "Email" },
                  { key: "ph_number", label: "Phone" },
                  { key: "College", label: "College" },
                  { key: "Exam_date", label: "Interview Date" },
                  { key: "Expiry", label: "Expiry Date" },
                ].map(({ key, label }) => (
                  <div
                    key={key}
                    className="grid grid-cols-4 items-center gap-4"
                  >
                    <Label htmlFor={key} className="text-right">
                      {label}
                    </Label>
                    <Input
                      id={key}
                      type={
                        ["Exam_date", "Expiry"].includes(key)
                          ? "datetime-local"
                          : "text"
                      }
                      value={
                        isEditing
                          ? (editedCandidate as any)[key]
                          : (selectedCandidate as any)[key]
                      }
                      onChange={(e) =>
                        isEditing &&
                        setEditedCandidate((prev) =>
                          prev ? { ...prev, [key]: e.target.value } : null
                        )
                      }
                      className="col-span-3"
                      readOnly={!isEditing}
                    />
                  </div>
                ))}
              </div>
              <DialogFooter>
                {isEditing ? (
                  <>
                    <Button
                      variant="outline"
                      onClick={() => setIsEditing(false)}
                      disabled={isLoading}
                    >
                      Cancel
                    </Button>
                    <Button onClick={handleSave} disabled={isLoading}>
                      {isLoading ? (
                        <>
                          <Loader
                            size="sm"
                            className="mr-2"
                            color="text-white"
                          />
                          Saving
                        </>
                      ) : (
                        "Save"
                      )}
                    </Button>
                  </>
                ) : (
                  <Button onClick={handleEdit}>Edit</Button>
                )}
              </DialogFooter>
            </motion.div>
          </DialogContent>
        </Dialog>
      )}
    </motion.div>
  );
};

export default CandidatesTable;
