"""
Records which canonical bullets/skills were selected for each application.

Called from generate_resume.py after the applications row is created.
Bullets and skills written as plain strings (old format) are silently skipped.
Dict format: bullets={'id': ..., 'text': ...}, skills={'id': ..., ...}
"""


def record_bullet_selections(conn, application_id, resume):
    """Insert bullet/skill selections into application_bullets/application_skills."""
    conn.execute("DELETE FROM application_bullets WHERE application_id = ?", (application_id,))
    conn.execute("DELETE FROM application_skills  WHERE application_id = ?", (application_id,))

    position = 0
    for section in ('experience', 'additional_experience'):
        for job in resume.get(section, []):
            for role_entry in job.get('roles', []):
                for b in role_entry.get('bullets', []):
                    if not (isinstance(b, dict) and 'id' in b):
                        continue
                    position += 1
                    canonical = conn.execute(
                        "SELECT text FROM bullets WHERE id = ?", (b['id'],)
                    ).fetchone()
                    text_override = None
                    if canonical and b.get('text', '').strip() != canonical['text'].strip():
                        text_override = b['text']
                    conn.execute(
                        "INSERT INTO application_bullets (application_id, bullet_id, position, text_override)"
                        " VALUES (?, ?, ?, ?)",
                        (application_id, b['id'], position, text_override),
                    )

    for i, skill in enumerate(resume.get('skills', []), 1):
        if not (isinstance(skill, dict) and 'id' in skill):
            continue
        canonical = conn.execute(
            "SELECT content FROM skills WHERE id = ?", (skill['id'],)
        ).fetchone()
        content_override = None
        if canonical and skill.get('content', '').strip() != canonical['content'].strip():
            content_override = skill['content']
        conn.execute(
            "INSERT INTO application_skills (application_id, skill_id, position, content_override)"
            " VALUES (?, ?, ?, ?)",
            (application_id, skill['id'], i, content_override),
        )
