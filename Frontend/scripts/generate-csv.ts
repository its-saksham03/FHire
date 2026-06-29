import { candidatesToCSV } from "../src/lib/api";
import { MOCK_CANDIDATES } from "../src/lib/mock-data";
import * as fs from "fs";
import * as path from "path";

const csv = candidatesToCSV(MOCK_CANDIDATES);
const outDir = path.join(process.cwd(), "public");
if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, "talentgraph-rankings.csv"), csv);
console.log("Wrote public/talentgraph-rankings.csv with", MOCK_CANDIDATES.length, "rows");
