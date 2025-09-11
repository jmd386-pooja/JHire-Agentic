const { PrismaClient } = require('@prisma/client');
const axios = require('axios');
const dotenv = require('dotenv');



dotenv.config();
import { prisma } from "@/lib/prisma";

const MISTRAL_API_URL = 'https://api.mistral.ai/v1/chat/completions';
const MISTRAL_API_KEY = process.env.MISTRAL_API_KEY;
const MISTRAL_AGENT_ID = process.env.MISTRAL_AGENT_ID;

console.log(' MISTRAL_API_KEY loaded:', MISTRAL_API_KEY);
console.log(' MISTRAL_AGENT_ID loaded:', process.env.MISTRAL_AGENT_ID);

async function getCategoryScores(skills) {
  const payload = {
  model: "mistral-medium",
  messages: [
  {
    role: "system",
    content: `
    You are a career evaluation assistant. Given the following resume details, analyze the candidate's overall suitability for the following roles based on all available information:

    - Data Scientist
    - Data Engineer
    - Full Stack Developer

    Return a JSON object with each role's relevance score (0-100), using this format:

    {
      "Data Scientist": 80,
      "Data Engineer": 65,
      "Full Stack Developer": 45
    }

    Consider their skills, education, projects, certifications, and experience.
    Respond ONLY with valid JSON. Do not include any explanation.
    `.trim()
      },
      {
        role: "user",
        content: `
    Resume Details:
    - Skills: ${skills.join(', ')}
    - Education: ${education}
    - Projects: ${projects.join(', ')}
    - Certifications: ${certifications.join(', ')}
    - Experience: ${experience}
        `.trim()
  }
],
  temperature: 0.2
};


  const headers = {
    Authorization: `Bearer ${MISTRAL_API_KEY}`,
    'Content-Type': 'application/json'
  };

  try {
    const agentId = process.env.MISTRAL_AGENT_ID; 
    const url = "https://api.mistral.ai/v1/chat/completions";

    const res = await axios.post(url, payload, { headers });

    console.error(" FULL MISTRAL RESPONSE:", JSON.stringify(res.data, null, 2));

    if (!res.data || !res.data.choices || !res.data.choices[0]) {
      throw new Error("Mistral API did not return valid choices");
    }

    const content = res.data.choices[0].message.content.trim();
    const cleaned = content.replace(/```json|```/g, "").trim();
    return JSON.parse(cleaned);

  } catch (err) {
    console.error(' Mistral agent call failed:', err.message);
    return null;
  }
}


async function run() {
  try {
    const candidates = await prisma.candidate.findMany({
      where: {
        categories: {
        none: {}
      },
        Skills: { isEmpty: false }
      }
    });

    for (const candidate of candidates) {
      console.log(` Classifying: ${candidate.name} (${candidate.email})`);
      const scores = await getCategoryScores(candidate.Skills);

      if (!scores) {
        console.warn(` Skipping ${candidate.name} due to API error`);
        continue;
      }

      // Extract all categories with score ≥ 80
      const highMatches = Object.entries(scores).filter(([_, score]) => score >= 80);

      let categoriesToStore = [];

      if (highMatches.length > 0) {
        categoriesToStore = highMatches;
      } else {
        // If none ≥ 80, use the top-scoring one
        const sorted = Object.entries(scores).sort((a, b) => b[1] - a[1]);
        categoriesToStore = [sorted[0]];
      }

      for (const [type, score] of categoriesToStore) {
        await prisma.category.create({
          data: {
            type: `${type} (${score}%)`,
            candidate: {
              connect: { id: candidate.id }
            }
          }
        });
        console.log(` ${candidate.name} → ${type} (${score}%)`);
      }
    }

    await prisma.$disconnect();
  } catch (err) {
    console.error(' Script error:', err.message);
    await prisma.$disconnect();
  }
}

run();
