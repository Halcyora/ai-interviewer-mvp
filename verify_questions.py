import json
from pathlib import Path

# Check a sample file
f = json.load(open('data/questions/meta_staff_engineer_questions.json'))
questions = f['questions']

beginner = sum(1 for q in questions if q['difficulty'] == 'beginner')
intermediate = sum(1 for q in questions if q['difficulty'] == 'intermediate')
advanced = sum(1 for q in questions if q['difficulty'] == 'advanced')

print(f'Sample File (meta_staff_engineer_questions.json):')
print(f'  Total: {len(questions)}')
print(f'  Beginner: {beginner}')
print(f'  Intermediate: {intermediate}')
print(f'  Advanced: {advanced}')

# Verify all 25 files
questions_dir = Path('data/questions')
files = sorted(questions_dir.glob('*_questions.json'))
print(f'\nAll 25 Files:')
print(f'Total files: {len(files)}')

all_good = True
for f in files:
    data = json.load(open(f))
    q_count = len(data.get('questions', []))
    if q_count != 60:
        print(f'  ✗ {f.name}: {q_count} questions (expected 60)')
        all_good = False

if all_good:
    print(f'  ✓ All 25 files have 60 questions each')
