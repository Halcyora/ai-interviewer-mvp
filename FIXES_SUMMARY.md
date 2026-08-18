# Interview System Fixes

## Issues Fixed

### 1. **Progress Bar Not Updating** ✅
**Problem:** Progress bar showed 0/X topics throughout the interview and never increased.

**Root Cause:** The `updateProgress()` function was only called when displaying the first question, but NOT when displaying subsequent questions after an answer was submitted.

**Solution:** 
- Added `updateProgress(data.next_question.turn_index, totalTopics)` in the `handleEvalResult()` function
- Progress bar now updates immediately after each answer is evaluated

### 2. **No 10-Minute Interview Timer** ✅
**Problem:** Interview had no time limit - users could take as long as they wanted.

**Solution Added:**
- New timer display in header (MM:SS format)
- Timer starts when interview begins
- Timer shows time remaining from 10:00 down to 0:00
- Timer turns RED when less than 1 minute remains
- Interview automatically ends when 10 minutes elapsed
- Timer is hidden when interview is not active

## Files Modified

### `/ui/static/app.js`
- Added `interviewStartTime` and `interviewTimerInterval` variables
- Added `MAX_INTERVIEW_DURATION_MS = 10 * 60 * 1000` constant
- Added `updateTimer()` function to track and display remaining time
- Updated `updateProgress()` to be called when displaying next question
- Updated `resetToMainPage()` to clear timer
- Updated `startInterview()` to show timer and start countdown
- Updated `handleEvalResult()` to:
  - Update progress bar with new question index
  - Stop timer when interview completes
  - Auto-end interview if time limit reached

### `/ui/templates/index.html`
- Added `<div id="timer-container">` with `<span id="interview-timer">`
- Timer is hidden by default and shown only during active interview

### `/ui/static/style.css`
- Added `#timer-container` styling (flex layout, monospace font)
- Added `#interview-timer` styling (monospace font family, min-width)

## User-Facing Changes

### Before:
- Progress bar static (0/10 topics) even after answering questions
- No time constraints on interview
- Users could spend unlimited time

### After:
- ✅ Progress bar updates after each answer (1/10, 2/10, 3/10, etc.)
- ✅ 10-minute countdown timer visible in header (MM:SS)
- ✅ Timer turns red at < 1 minute warning
- ✅ Auto-ends interview when time runs out
- ✅ Better UX: users know how much time/progress remains

## Testing Checklist
- [ ] Start new interview and verify timer displays 10:00
- [ ] Answer a question and verify progress bar updates
- [ ] Monitor timer countdown in real-time
- [ ] Leave interview before 10 minutes and verify timer stops
- [ ] Complete interview before 10 minutes
- [ ] (Optional) Wait 10 minutes to test auto-end (or fast-forward in devtools)
