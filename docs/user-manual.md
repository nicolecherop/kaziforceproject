# User manual

Start the application from the project folder:

```powershell
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Visit http://127.0.0.1:8000/. If setup created demo data, credentials are in `.local/demo-accounts.txt`. Keep this local file private.

If the app is already running at that address, open it directly rather than starting a second server. The first matching request after a server restart can take longer while the language resources and ESCO index load.

## Candidate walkthrough

1. Choose **Get started**, enter account details and choose **Candidate**. Sign in with the username, not the email address.
2. Open **My profile**. Add a headline, summary, skills, qualifications, certifications, experience and optional portfolio URL.
3. Optionally attach a TXT, DOCX or PDF resume, up to 5 MB. TXT/DOCX text is extracted; recognised section headings can fill fields that were empty. Save, then review the extracted fields. PDF attachments need their text pasted into **Resume text for matching** or represented in the profile fields.
4. Select **Discoverable** only if you want recruiters to see your profile in general candidate searches. Otherwise, applying shares it with the recruiter for that role.
5. Open **My job matches** for up to 10 open, unexpired roles. Expand **Understand this match** to inspect shared terms and skill gaps. The percentage is similarity, not a hiring probability.
6. Open **Explore jobs** to search by role, company, location or employment type. A job detail page lists its requirements and recruiter priorities.
7. Before applying, add skills and qualifications to your profile. Submit an optional cover note using **Apply for this role**. Repeated clicks do not create duplicate applications.
8. Open **Applications** to follow status history. You can withdraw an active application. A withdrawn application remains in history and cannot be resubmitted through a duplicate entry.
9. Use **Account settings** to change your password. Sign out with the arrow beside your account name.

## Recruiter walkthrough

1. Register with the **Recruiter** role and complete **Organisation**.
2. Choose **Create a job**, fill the role description, qualifications, experience and other details.
3. Optionally search for an ESCO occupation. Under **Skills & priorities**, type at least two characters into the search box, then choose the returned concept in the dropdown.
4. Set each priority from 1 (normal) to 5 (most important). Use **Add another skill** for more requirements. Select **Essential** where appropriate. It highlights gaps without automatically excluding a candidate.
5. Save the role as a draft, open posting or closed posting. Only open and unexpired roles accept applications and appear in candidate recommendations.
6. Open **My job postings → Top candidates** to see up to 10 discoverable candidates and applicants to your own role. Expand explanations, inspect profiles and download resumes where access is allowed.
7. Use **Export top 10** for a CSV ranking snapshot.
8. Open **Applications** to review a candidate's note and update status. The system records every accepted status change.
9. Close a role when it should stop accepting applications. Existing applications remain available for review.

## Administrator walkthrough

1. Sign in with the generated administrator account, or create your own with `manage.py createsuperuser`.
2. Visit `/admin/`. Manage user accounts and staff permissions carefully. Public registration never grants administration rights.
3. Review or moderate postings and profiles. Deactivate accounts that should no longer participate.
4. Inspect ESCO skills and occupations. Import official updates through `manage.py import_esco` rather than manually replacing concept URIs.
5. Inspect saved match results and application events. Application-state changes should go through the recruiter workflow so history remains consistent.

## Demonstration sequence

Use the fictional demo candidate to show a profile, recommendations, a match explanation and an application. Sign out and use the demo recruiter to open candidate rankings, change a skill priority, rerun ranking and update an application status. Return as the candidate to show the updated timeline. Use the administrator account last to show the database-backed management screens.

The data is stored in Neon while the website runs on the local Django server. This prototype does not send application emails, scrape job boards, verify credentials or make automated hiring decisions.
