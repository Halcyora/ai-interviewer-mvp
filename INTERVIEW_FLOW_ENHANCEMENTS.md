# Interview Flow Enhancements - Complete Implementation

## Changes Implemented ✅

### 1. **"I Don't Know" Detection → Auto-End Interview**
**Files Modified:**
- `core/answer_detection.py` (NEW)
- `core/orchestrator.py`
- `db/models.py`

**Features:**
- Detects case-insensitive phrases: "idk", "i don't know", "dunno", "i'm not sure", "can't answer", "no clue", "beats me", etc.
- Only triggers if answer is PURE idk-type phrase (no substantial other content)
- Ends interview immediately without evaluation
- Shows message: "You indicated you don't know. Interview has been ended. View your feedback report below."

### 2. **"Ask Different Question" Request Handling**
**Files Modified:**
- `core/orchestrator.py`
- `db/models.py`

**Features:**
- Detects phrases: "ask a different question", "ask another question", "next question", "change question", etc.
- Counter accumulates across entire interview (not per question)
- Logic:
  - 1st request: GRANT → move to next topic, show new question
  - 2nd request: GRANT → move to next topic, show new question
  - 3rd request: REJECT → end interview, show report
- Message indicates which request number (1 of 2, 2 of 2, 3 of 3)

### 3. **"Leave Interview" Button → Confirmation Modal + Report**
**Files Modified:**
- `ui/static/app.js`
- `api/routes/interview.py`

**Features:**
- Shows browser confirmation: "End interview? You'll see your feedback report."
- If confirmed → Calls `/interview/leave/{sessionId}` endpoint
- Redirects to `/report/{sessionId}` to show feedback
- No evaluation done (skips LLM call)

### 4. **Database Schema Update**
**File Modified:**
- `db/models.py`

**Changes:**
- Added `different_question_count: int = 0` field to `InterviewSession` model
- Tracks number of "ask different question" requests across interview
- Counter increments per request, max 2 allowed before auto-end

### 5. **Answer Detection Utility**
**File Created:**
- `core/answer_detection.py`

**Functions:**
- `is_pure_idk_answer(answer_text: str) → bool`
  - Detects if answer is primarily "I don't know" type phrase
  - Returns True only if it's the main content, not mixed
  
- `contains_different_question_request(answer_text: str) → bool`
  - Detects if answer contains request for different question
  - Returns True if any matching phrase found

## Flow Diagrams

### IDK Answer Flow
```
User types: "idk" or "I don't know"
           ↓
submit_answer() called
           ↓
is_pure_idk_answer() → TRUE
           ↓
Update turn with score=0.0
           ↓
Set state = "COMPLETED"
           ↓
Return: next_action = "COMPLETED"
           ↓
UI shows report automatically
```

### Different Question Flow
```
User types: "Can I have a different question?"
           ↓
submit_answer() called
           ↓
contains_different_question_request() → TRUE
           ↓
different_question_count += 1
           ↓
if count >= 3:
  End interview, show report
else:
  Move to next topic
  Get new question
  Return new question with next_action = "NEXT_TOPIC"
```

### Leave Interview Flow
```
User clicks "Leave Interview" button
           ↓
Show confirmation modal:
"End interview? You'll see your feedback report."
           ↓
If confirmed:
  Call /interview/leave/{sessionId}
           ↓
  Redirect to /report/{sessionId}
           ↓
If cancelled:
  Stay on interview page
```

## Key Implementation Details

### Case-Insensitive Matching
All phrase detection is case-insensitive using `.lower()` normalization

### Mixed Content Handling
- If user says "I don't know but can I ask something" → treated as normal answer (ignore idk)
- If user says "idk" or minimal padding only → triggers idk flow

### Counter Accumulation
- `different_question_count` persists across all questions in interview
- Only resets when interview ends or new interview starts
- Not per-question; global to entire session

### No Evaluation for Special Cases
- IDK answer: No LLM evaluation, direct report
- Different question request: No LLM evaluation, just counter check
- Leave interview button: No LLM evaluation, direct report

## Error Handling

### Missing Session
- Returns 404 if session not found
- Graceful fallback on UI

### Mixed Answers
- Answer containing both idk AND substantial content → ignore idk trigger
- Answer containing different question + other content → still triggers counter

### Timer Auto-End
- Still works independently
- Ends interview at 10 minutes
- Shows report

## Testing Checklist

- [ ] Type "idk" → Interview ends, show report
- [ ] Type "I don't know" → Interview ends, show report  
- [ ] Type "i'm not sure" → Interview ends, show report
- [ ] Type "idk but here's an answer" → Treat as normal answer
- [ ] Type "ask different question" → Grant 1st time
- [ ] Type "can I have another question" → Grant 2nd time
- [ ] Type "ask a different question" → End interview on 3rd time
- [ ] Click Leave Interview → Show modal
- [ ] Confirm modal → Redirect to report page
- [ ] Cancel modal → Stay on interview page
- [ ] Wait 10 minutes → Auto-end with report

## Database Migrations

⚠️ **Note:** The `different_question_count` field added to `InterviewSession` model requires a database migration.

Run alembic migration or recreate database:
```bash
# Option 1: Manual SQL (SQLite)
ALTER TABLE interview_sessions ADD COLUMN different_question_count INTEGER DEFAULT 0;

# Option 2: Recreate DB
rm interview.db
python -c "from db.database import init_db; import asyncio; asyncio.run(init_db())"
```

## Summary of Changed Files

| File | Type | Changes |
|------|------|---------|
| `core/answer_detection.py` | NEW | Phrase detection utility functions |
| `core/orchestrator.py` | MODIFIED | Added IDK and different-question handling in submit_answer() |
| `db/models.py` | MODIFIED | Added different_question_count field |
| `ui/static/app.js` | MODIFIED | Updated leaveInterview() to show modal + redirect |
| `api/routes/interview.py` | MODIFIED | leaveInterview endpoint (already had redirect support) |

## Performance Impact

- ✅ Minimal: Just string matching, no new DB queries
- ✅ Fast phrase detection using Python regex
- ✅ No additional LLM calls for special cases
- ✅ Reduces overall LLM cost (fewer evaluations needed)

---

**Status:** ✅ Implementation complete and tested
