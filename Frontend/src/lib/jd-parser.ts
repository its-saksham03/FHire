export interface RequirementSummary {
  role: string;
  seniority: "Senior" | "Junior" | "Mid-level";
  experience: string;
  location: string;
  remoteHybrid: "Remote" | "Hybrid" | "Onsite" | "Not specified";
  employmentType: "Full-time" | "Contract" | "Not specified";
  noticePeriod: string;
  skills: string[];
  keywords: string[];
}

export function parseJobDescription(text: string): RequirementSummary {
  const normalized = text.replace(/\s+/g, " ");
  const lowerText = normalized.toLowerCase();

  // 1. Detected Role
  let role = "Not specified";
  const standardRoles = [
    "ai engineer", "ml engineer", "machine learning engineer", "prompt engineer",
    "data engineer", "platform engineer", "devops engineer", "site reliability engineer",
    "software engineer", "research engineer", "security engineer", "cloud engineer",
    "product manager"
  ];
  
  for (const stdRole of standardRoles) {
    if (new RegExp(`\\b${stdRole}\\b`, "i").test(lowerText)) {
      role = stdRole.split(" ").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
      break;
    }
  }

  if (role === "Not specified") {
    const roleRegex = /\b([A-Za-z\s-]{1,40}\b(?:engineer|developer|scientist|manager|designer|analyst|architect)\b[A-Za-z\s-]{0,30})/i;
    const roleMatch = normalized.match(roleRegex);
    if (roleMatch && roleMatch[1]) {
      role = roleMatch[1].trim();
    }
  }

  // 2. Seniority
  let seniority: "Senior" | "Junior" | "Mid-level" = "Mid-level";
  if (/\b(?:senior|lead|principal|staff|head\s+of|director)\b/.test(lowerText)) {
    seniority = "Senior";
  } else if (/\b(?:junior|associate|entry|intern)\b/.test(lowerText)) {
    seniority = "Junior";
  }

  // 3. Experience Normalization
  let experience = "Not specified";
  const expRegex = /(?:minimum|min|at\s+least|required)?\s*(\d+(?:\s*(?:-|to|\+)\s*\d+)?)\s*(?:years?|yrs?)/i;
  const expMatch = normalized.match(expRegex);
  if (expMatch && expMatch[1]) {
    let rawExp = expMatch[1].replace(/\s+/g, "").toLowerCase();
    rawExp = rawExp.replace("to", "-");
    if (!rawExp.includes("+") && !rawExp.includes("-")) {
      const matchIndex = expMatch[0].toLowerCase();
      if (matchIndex.includes("minimum") || matchIndex.includes("min") || matchIndex.includes("least")) {
        rawExp = `${rawExp}+`;
      }
    }
    experience = `${rawExp} years`;
  }

  // 4. Location Detection
  let location = "Not specified";
  const locRegexes = [
    /location:\s*([A-Za-z\s]+)/i,
    /based in\s*([A-Za-z\s]+)/i,
    /work location\s*(?:is|:)?\s*([A-Za-z\s]+)/i
  ];
  
  for (const regex of locRegexes) {
    const match = normalized.match(regex);
    if (match && match[1]) {
      location = match[1].trim().split(",")[0].trim();
      break;
    }
  }

  if (location === "Not specified") {
    const cities = ["bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "pune", "chennai", "noida", "gurgaon", "gurugram", "remote"];
    for (const city of cities) {
      if (new RegExp(`\\b${city}\\b`, "i").test(lowerText)) {
        location = city.charAt(0).toUpperCase() + city.slice(1);
        break;
      }
    }
  }

  // 5. Remote/Hybrid/Onsite
  let remoteHybrid: "Remote" | "Hybrid" | "Onsite" | "Not specified" = "Not specified";
  if (/\b(?:remote|work\s+from\s+home|wfh)\b/.test(lowerText)) {
    remoteHybrid = "Remote";
  } else if (/\b(?:hybrid|flexible\s+work)\b/.test(lowerText)) {
    remoteHybrid = "Hybrid";
  } else if (/\b(?:onsite|on-site|in\s+office|in-office)\b/.test(lowerText)) {
    remoteHybrid = "Onsite";
  }

  // 6. Employment Type
  let employmentType: "Full-time" | "Contract" | "Not specified" = "Not specified";
  if (/\b(?:full-time|full\s+time|permanent)\b/.test(lowerText)) {
    employmentType = "Full-time";
  } else if (/\b(?:contract|contractor|temporary|temp)\b/.test(lowerText)) {
    employmentType = "Contract";
  }

  // 7. Notice Period
  let noticePeriod = "Not specified";
  if (/\b(?:immediate\s*joiner|immediate\s*start|immediately)\b/i.test(normalized)) {
    noticePeriod = "Immediate";
  } else {
    const noticeRegex = /\b(\d+\s*(?:days?|weeks?|months?))\s*notice\b/i;
    const noticeMatch = normalized.match(noticeRegex);
    if (noticeMatch && noticeMatch[1]) {
      noticePeriod = noticeMatch[1].trim();
    }
  }

  // 8. Dynamic Technical Skills Extraction
  const skillDictionary: Record<string, string[]> = {
    "PyTorch": ["pytorch"],
    "TensorFlow": ["tensorflow"],
    "LLM": ["llm", "large language model", "gpt", "transformers"],
    "RAG": ["rag", "retrieval-augmented generation", "retrieval augmented generation"],
    "LangChain": ["langchain"],
    "Fine-tuning": ["fine-tuning", "finetuning", "lora", "peft"],
    "Vector Search": ["vector search", "vector database", "embeddings", "milvus", "pinecone", "chroma", "faiss"],
    "MLOps": ["mlops", "model serving", "kubeflow", "mlflow"],
    "Python": ["python"],
    "TypeScript": ["typescript", "ts"],
    "Go": ["golang", "go language", " go "],
    "Rust": ["rust"],
    "Docker": ["docker", "container"],
    "Kubernetes": ["kubernetes", "k8s"],
    "CI/CD": ["ci/cd", "github actions", "jenkins"],
    "PostgreSQL": ["postgresql", "postgres"],
    "Redis": ["redis"],
    "Kafka": ["kafka"]
  };

  const detectedSkillsSet = new Set<string>();
  for (const [skillName, synonyms] of Object.entries(skillDictionary)) {
    for (const syn of synonyms) {
      if (new RegExp(syn.startsWith(" ") ? syn : `\\b${syn}\\b`, "i").test(lowerText)) {
        detectedSkillsSet.add(skillName);
        break;
      }
    }
  }
  let skills = Array.from(detectedSkillsSet);
  if (skills.length === 0) {
    skills = ["Python", "Machine Learning"]; // default fallback skills
  }

  // 9. Non-Skill Keywords Extraction
  const keywordDict = [
    "production", "scale", "distributed systems", "microservices",
    "architecture", "fast-paced", "ownership", "leadership",
    "agile", "optimization", "startup"
  ];
  const detectedKeywords: string[] = [];
  for (const kw of keywordDict) {
    if (new RegExp(`\\b${kw}\\b`, "i").test(lowerText)) {
      detectedKeywords.push(kw.charAt(0).toUpperCase() + kw.slice(1));
    }
  }

  return {
    role,
    seniority,
    experience,
    location,
    remoteHybrid,
    employmentType,
    noticePeriod,
    skills,
    keywords: detectedKeywords,
  };
}
