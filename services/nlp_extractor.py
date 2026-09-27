import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple

import dateparser
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Load spaCy safely
try:
    import spacy
    try:
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        nlp = spacy.blank("en")
except Exception:
    nlp = None

# Common action verbs that signal tasks
ACTION_VERBS = {
    "prepare", "send", "review", "complete", "finish", "update", "create", "build",
    "deploy", "test", "fix", "check", "submit", "write", "organize", "schedule",
    "finalize", "contact", "call", "email", "draft", "verify", "present", "deliver",
    "investigate", "audit", "follow", "share", "implement", "coordinate", "resolve",
    "setup", "configure", "publish", "document", "analyze", "design", "refactor"
}

# Words that should not be mistaken for human names
INVALID_NAMES = {
    "the", "this", "that", "it", "we", "i", "you", "they", "he", "she", "team",
    "someone", "anyone", "everyone", "nobody", "everybody", "all", "today", "tomorrow",
    "yesterday", "friday", "monday", "tuesday", "wednesday", "thursday", "saturday", "sunday",
    "action", "item", "meeting", "status", "deadline", "task", "project", "client",
    "qa", "backend", "frontend", "devops", "design", "lead", "product", "manager",
    "good", "great", "please", "thanks", "hello", "hi", "from", "on", "in", "at", "by"
}

# Regex pattern for deadline extraction
DEADLINE_PATTERNS = [
    # "by Friday", "by tomorrow", "by next Wednesday", "by 5 PM tomorrow"
    r"(?i)\b(?:by|before|until|due|on|no\s+later\s+than)\s+((?:the\s+end\s+of\s+(?:the\s+)?day|eod|cob|today|tomorrow|\d{1,2}(?::\d{2})?\s*(?:am|pm)?(?:\s+(?:today|tomorrow|\w+day))?|(?:next\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?:\s+\d{2,4})?|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?))\b",
    # Standalone "tomorrow", "next week", "next Friday" at the end of sentence
    r"(?i)\b(tomorrow|next\s+(?:week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b"
]

def parse_deadline(text: str) -> Tuple[str, Optional[date]]:
    """
    Extracts deadline substring and parses it into a datetime.date object.
    Returns (raw_deadline_str, parsed_date).
    """
    raw_deadline = None
    for pattern in DEADLINE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            raw_deadline = match.group(1).strip()
            break

    if not raw_deadline:
        return "Not specified", None

    # Parse with dateparser
    # Set relative date reference
    now = datetime.now()
    parsed_dt = dateparser.parse(
        raw_deadline,
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": now
        }
    )

    if parsed_dt:
        # If relative date was in past due to weekday calculation, ensure it moves to the upcoming occurrence
        if parsed_dt.date() < now.date() and any(w in raw_deadline.lower() for w in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
            parsed_dt += timedelta(days=7)
        return raw_deadline, parsed_dt.date()

    return raw_deadline, None


def clean_task_text(task_raw: str, deadline_str: str = "") -> str:
    """Cleans task string, removes aux words, trailing deadlines and punctuation."""
    task = task_raw.strip()

    # Remove leading auxiliary phrases
    task = re.sub(r"^(?:will|shall|to|needs\s+to|need\s+to|must|should|has\s+to|have\s+to|is\s+going\s+to|commits\s+to|plans\s+to|can)\s+", "", task, flags=re.IGNORECASE)
    task = re.sub(r"^(?:is|are|was|were)\s+responsible\s+for\s+", "", task, flags=re.IGNORECASE)
    task = re.sub(r"^(?:make\s+sure\s+to|please|ensure\s+that|don't\s+forget\s+to|take\s+care\s+of)\s+", "", task, flags=re.IGNORECASE)

    # Remove extracted deadline from the end of the task if present
    if deadline_str and deadline_str != "Not specified":
        # Escape deadline string for regex
        dl_escaped = re.escape(deadline_str)
        task = re.sub(rf"(?i)\s*(?:by|before|until|due|on|no\s+later\s+than)?\s*{dl_escaped}\b.*$", "", task)

    # Strip conversational trailing clauses like "so the frontend team has everything", "before we do X"
    # Only if preceded by punctuation or comma
    task = re.sub(r",\s*(?:so\s+that|so|in\s+order\s+to|before).*$", "", task, flags=re.IGNORECASE)

    # Clean leading/trailing punctuation and whitespace
    task = re.sub(r"^[\s,:\-–]+", "", task)
    task = re.sub(r"[\s,:\-–.]+$", "", task)

    if not task:
        return "Unspecified task"

    # Capitalize the first letter
    task = task[0].upper() + task[1:]
    return task


def extract_owner_from_text(sentence: str, speaker: Optional[str] = None) -> str:
    """
    Extracts person/owner name from sentence or speaker context.
    """
    # 1. First-person patterns ("I'll...", "I will...", "I am going to...")
    first_person_match = re.search(r"\b(?:I'll|I\s+will|I'm\s+going\s+to|I\s+can|I\s+am\s+responsible\s+for)\b", sentence, re.IGNORECASE)
    if first_person_match and speaker and speaker.lower() not in INVALID_NAMES:
        return speaker

    # 2. Explicit patterns like "Arun will...", "Priya is responsible for...", "John needs to..."
    explicit_match = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:will|needs\s+to|must|should|is\s+responsible\s+for|has\s+to|commits\s+to)\b", sentence)
    if explicit_match:
        candidate = explicit_match.group(1).strip()
        if candidate.lower() not in INVALID_NAMES:
            return candidate

    # 3. Explicit assignment: "Assigned to Arun", "Action item for Priya"
    assigned_match = re.search(r"\b(?:assigned\s+to|action\s+item\s+for|owner:\s*)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", sentence, re.IGNORECASE)
    if assigned_match:
        candidate = assigned_match.group(1).strip()
        if candidate.lower() not in INVALID_NAMES:
            return candidate

    # 4. Use spaCy NER if available
    if nlp:
        try:
            doc = nlp(sentence)
            for ent in doc.ents:
                if ent.label_ == "PERSON" and ent.text.strip().lower() not in INVALID_NAMES:
                    return ent.text.strip()
        except Exception:
            pass

    # If first person but no speaker known, return Unassigned
    return "Unassigned"


def calculate_confidence(task: str, owner: str, deadline: str, sentence: str) -> float:
    """
    Calculates a calibrated extraction confidence score between 0.35 and 0.98.
    """
    score = 0.45  # Base score for matching an action pattern

    lower_task = task.lower()
    lower_sent = sentence.lower()

    # Boost if task contains known action verbs
    words = set(re.findall(r"\b\w+\b", lower_task))
    if any(verb in words for verb in ACTION_VERBS):
        score += 0.20
    elif any(verb in lower_sent for verb in ACTION_VERBS):
        score += 0.10

    # Owner validation
    if owner and owner != "Unassigned":
        score += 0.20
    else:
        score -= 0.15

    # Deadline validation
    if deadline and deadline != "Not specified":
        score += 0.15
    else:
        score -= 0.08

    # Syntactic indicators (length, modal keywords)
    if any(m in lower_sent for m in ["will", "needs to", "responsible for", "must", "should", "complete", "prepare"]):
        score += 0.08

    if 3 <= len(task.split()) <= 15:
        score += 0.05

    # Clamp confidence
    score = max(0.35, min(0.98, score))
    return round(score, 2)


def detect_duplicates(action_items: List[Dict[str, Any]], threshold: float = 0.75) -> None:
    """
    Marks duplicates among a list of extracted action item dicts using TF-IDF cosine similarity.
    Updates the 'is_duplicate' key in place.
    """
    if len(action_items) < 2:
        return

    tasks = [item["task"] for item in action_items]
    try:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(tasks)
        sim_matrix = cosine_similarity(tfidf_matrix)

        for i in range(len(action_items)):
            for j in range(i + 1, len(action_items)):
                sim = sim_matrix[i, j]
                # If high similarity or identical task string
                if sim >= threshold or tasks[i].lower() == tasks[j].lower():
                    action_items[j]["is_duplicate"] = True
    except Exception:
        # Fallback to normalized string comparison
        seen = set()
        for item in action_items:
            norm = re.sub(r"\W+", " ", item["task"].lower()).strip()
            if norm in seen:
                item["is_duplicate"] = True
            else:
                seen.add(norm)

    # Refresh validation messages for duplicates
    for item in action_items:
        if item.get("is_duplicate"):
            msgs = []
            if item.get("missing_owner"):
                msgs.append("Missing owner")
            if item.get("missing_deadline"):
                msgs.append("Missing deadline")
            msgs.append("Potential duplicate task")
            item["validation_message"] = "; ".join(msgs)


def extract_action_items(transcript: str, similarity_threshold: float = 0.75) -> List[Dict[str, Any]]:
    """
    Dynamically extracts action items, owners, deadlines, confidence, and validation flags
    from meeting transcript text.
    """
    if not transcript or not transcript.strip():
        return []

    lines = transcript.split("\n")
    action_items: List[Dict[str, Any]] = []

    current_speaker = None

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        # Check for speaker prefix e.g. "David (Product Lead): ...", "Sarah: ..."
        speaker_match = re.match(r"^([A-Z][a-zA-Z0-9_\s\(\)]+?)\s*:\s*(.*)$", line_clean)
        if speaker_match:
            speaker_raw = speaker_match.group(1).strip()
            # Clean speaker name (remove parenthetical role like '(Product Lead)')
            clean_speaker = re.sub(r"\s*\(.*?\)", "", speaker_raw).strip()
            if clean_speaker.lower() not in INVALID_NAMES and len(clean_speaker.split()) <= 3:
                current_speaker = clean_speaker
            line_content = speaker_match.group(2).strip()
        else:
            line_content = line_clean

        # Split content into sentences
        # Simple regex sentence splitter that preserves sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", line_content)

        for sent in sentences:
            sent_str = sent.strip()
            if not sent_str or len(sent_str) < 10:
                continue

            # Check if this sentence contains an action commitment
            matched = False
            candidate_task = None
            candidate_owner = None

            # Pattern 1: "[Person] will [task]"
            m1 = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:will|shall)\s+(.+?)(?:$|[.!?])", sent_str, re.IGNORECASE)
            if m1 and m1.group(1).lower() not in INVALID_NAMES:
                candidate_owner = m1.group(1)
                candidate_task = m1.group(2)
                matched = True

            # Pattern 2: "[Person] is responsible for [task]"
            if not matched:
                m2 = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+is\s+responsible\s+for\s+(.+?)(?:$|[.!?])", sent_str, re.IGNORECASE)
                if m2 and m2.group(1).lower() not in INVALID_NAMES:
                    candidate_owner = m2.group(1)
                    raw_subj = m2.group(2).strip()
                    # e.g. "the presentation" -> "Prepare the presentation" or "Presentation"
                    if not any(raw_subj.lower().startswith(v) for v in ACTION_VERBS):
                        candidate_task = f"Responsible for {raw_subj}"
                    else:
                        candidate_task = raw_subj
                    matched = True

            # Pattern 3: "[Person] needs to / must / should [task]"
            if not matched:
                m3 = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:needs\s+to|must|should|has\s+to)\s+(.+?)(?:$|[.!?])", sent_str, re.IGNORECASE)
                if m3 and m3.group(1).lower() not in INVALID_NAMES:
                    candidate_owner = m3.group(1)
                    candidate_task = m3.group(2)
                    matched = True

            # Pattern 4: First person "I'll / I will / I'm going to [task]"
            if not matched:
                m4 = re.search(r"\b(?:I'll|I\s+will|I'm\s+going\s+to)\s+(.+?)(?:$|[.!?])", sent_str, re.IGNORECASE)
                if m4:
                    candidate_owner = current_speaker if current_speaker else "Unassigned"
                    candidate_task = m4.group(1)
                    matched = True

            # Pattern 5: Collective / imperative "We must / We need to / Ensure that / Make sure to [task]"
            if not matched:
                m5 = re.search(r"\b(?:We\s+must|We\s+need\s+to|We\s+have\s+to|Make\s+sure\s+to|Please|Ensure\s+that)\s+(.+?)(?:$|[.!?])", sent_str, re.IGNORECASE)
                if m5:
                    candidate_owner = "Unassigned"
                    candidate_task = m5.group(1)
                    matched = True

            # Pattern 6: Passive "[Task/Entity] needs to be [verb]" e.g. "The security audit checklist needs to be updated."
            if not matched:
                m6 = re.search(r"^(.*?)\s+(?:needs\s+to\s+be|must\s+be|should\s+be|has\s+to\s+be)\s+([a-z]+ed|done|fixed|checked|reviewed|updated)(.*)$", sent_str, re.IGNORECASE)
                if m6:
                    item_subj = m6.group(1).strip()
                    verb_past = m6.group(2).strip()
                    extra = m6.group(3).strip()
                    
                    # Convert passive to active action phrase
                    verb_base = verb_past
                    if verb_past.endswith("ed"):
                        verb_base = verb_past[:-2]
                        if verb_base.endswith("at"):
                            verb_base += "e"  # updated -> update
                        elif verb_past in ["reviewed", "configured", "scheduled"]:
                            verb_base = verb_past[:-1] if verb_past.endswith("ed") else verb_past
                    
                    candidate_owner = "Unassigned"
                    candidate_task = f"{verb_past.capitalize()} {item_subj} {extra}".strip()
                    matched = True

            # If an action item was matched, process fields
            if matched and candidate_task:
                # Extract deadline and parsed date
                deadline_str, deadline_date = parse_deadline(sent_str)

                # Clean task text
                clean_task = clean_task_text(candidate_task, deadline_str)

                # Refine owner if needed
                final_owner = candidate_owner or extract_owner_from_text(sent_str, current_speaker)
                if not final_owner or final_owner.lower() in INVALID_NAMES:
                    final_owner = "Unassigned"

                # Calculate confidence score
                confidence = calculate_confidence(clean_task, final_owner, deadline_str, sent_str)

                # Validation flags
                missing_owner = (final_owner == "Unassigned")
                missing_deadline = (deadline_str == "Not specified")

                val_msgs = []
                if missing_owner:
                    val_msgs.append("Missing owner")
                if missing_deadline:
                    val_msgs.append("Missing deadline")
                validation_message = "; ".join(val_msgs) if val_msgs else None

                action_items.append({
                    "task": clean_task,
                    "owner": final_owner,
                    "deadline": deadline_str,
                    "deadline_date": deadline_date,
                    "status": "Pending",
                    "confidence": confidence,
                    "source_sentence": sent_str,
                    "validation_message": validation_message,
                    "missing_owner": missing_owner,
                    "missing_deadline": missing_deadline,
                    "is_duplicate": False
                })

    # Run duplicate detection across all extracted items
    detect_duplicates(action_items, threshold=similarity_threshold)

    return action_items
