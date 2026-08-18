import sqlite3

# Check if database exists and verify schema
db_path = 'interview.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get table info
cursor.execute("PRAGMA table_info(interview_sessions);")
columns = cursor.fetchall()

print('✅ Database file: interview.db')
print()
print('📊 interview_sessions table schema:')
for col in columns:
    col_id, name, type_, notnull, default, pk = col
    marker = '✓ PK' if pk else ''
    print(f'   {name:30} {type_:10} {marker}'.strip())

# Verify different_question_count exists
has_counter = any(col[1] == 'different_question_count' for col in columns)
if has_counter:
    print()
    print('✅ NEW FIELD VERIFIED: different_question_count field exists!')
else:
    print()
    print('❌ ERROR: different_question_count field NOT found!')

conn.close()
