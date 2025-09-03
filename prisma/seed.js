"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g = Object.create((typeof Iterator === "function" ? Iterator : Object).prototype);
    return g.next = verb(0), g["throw"] = verb(1), g["return"] = verb(2), typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (g && (g = 0, op[0] && (_ = 0)), _) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
Object.defineProperty(exports, "__esModule", { value: true });
// prisma/seed.ts
var client_1 = require("@prisma/client");
var prisma = new client_1.PrismaClient();
function main() {
    return __awaiter(this, void 0, void 0, function () {
        return __generator(this, function (_a) {
            switch (_a.label) {
                case 0: 
                // Seed Candidate Scores
                return [4 /*yield*/, prisma.candidateScore.createMany({
                        data: [
                            {
                                job_id: 2,
                                candidate_name: "Jane Doe",
                                resume_email: "jane@mail.com",
                                final_score: 95,
                                final_rank: 1,
                                detailed_reasoning: "Strong technical background, clear answers.",
                                strengths: "Python, problem solving, communication",
                                weaknesses: "Needs more cloud exposure",
                                recommendation: "Strongly recommend",
                            },
                            {
                                job_id: 3,
                                candidate_name: "John Smith",
                                resume_email: "john@mail.com",
                                final_score: 82,
                                final_rank: 2,
                                detailed_reasoning: "Solid fundamentals but less confident in system design.",
                                strengths: "SQL, ETL, teamwork",
                                weaknesses: "Limited ML exposure",
                                recommendation: "Recommend with reservations",
                            },
                            {
                                job_id: 3,
                                candidate_name: "Smith",
                                resume_email: "joh@mail.com",
                                final_score: 70,
                                final_rank: 3,
                                detailed_reasoning: "Solid fundamentals but less confident in system design.",
                                strengths: "SQL teamwork",
                                weaknesses: "Limited exposure",
                                recommendation: "Recommend with reservations",
                            },
                            {
                                job_id: 3,
                                candidate_name: "John",
                                resume_email: "john@mail.com",
                                final_score: 77,
                                final_rank: 2,
                                detailed_reasoning: "Solid fundamentals but less confident in system design.",
                                strengths: "SQL, ETL, teamwork",
                                weaknesses: "Limited ML exposure",
                                recommendation: "Recommend with reservations",
                            },
                        ],
                    })];
                case 1:
                    // Seed Candidate Scores
                    _a.sent();
                    // Seed Job Descriptions
                    return [4 /*yield*/, prisma.jobDescription.createMany({
                            data: [
                                {
                                    job_description: "Data Scientist with experience in machine learning and Python.",
                                    role_category: "Data Science",
                                    categorization_confidence: 0.92,
                                    categorization_reasoning: "Focuses on ML and Python, clear Data Science role",
                                    key_indicators: JSON.stringify({ skills: ["Python", "Machine Learning", "Statistics"] }),
                                    total_candidates_evaluated: 0,
                                },
                                {
                                    job_description: "Data Engineer experienced in ETL pipelines and SQL.",
                                    role_category: "Data Engineering",
                                    categorization_confidence: 0.88,
                                    categorization_reasoning: "Mentions ETL, pipelines, and SQL, common for Data Engineering",
                                    key_indicators: { skills: ["ETL", "SQL", "Big Data"] },
                                    total_candidates_evaluated: 0,
                                },
                                {
                                    job_description: "Data Engineer experienced in databricks and SQL.",
                                    role_category: "Data Engineering",
                                    categorization_confidence: 0.80,
                                    categorization_reasoning: "Mentions ETL, databricks, and SQL, common for Data Engineering",
                                    key_indicators: JSON.stringify({ skills: ["ETL", "SQL", "Big Data"] }),
                                    total_candidates_evaluated: 0,
                                },
                            ],
                        })];
                case 2:
                    // Seed Job Descriptions
                    _a.sent();
                    return [2 /*return*/];
            }
        });
    });
}
main()
    .then(function () { return prisma.$disconnect(); })
    .catch(function (e) { return __awaiter(void 0, void 0, void 0, function () {
    return __generator(this, function (_a) {
        switch (_a.label) {
            case 0:
                console.error(e);
                return [4 /*yield*/, prisma.$disconnect()];
            case 1:
                _a.sent();
                process.exit(1);
                return [2 /*return*/];
        }
    });
}); });
