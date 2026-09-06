import csv
from collections import Counter
from typing import List, Dict, Tuple

DATA_FILE = "data/job_dataset.csv"

COL_TITLE = "Job Title"
COL_SKILLS = "Skills"
COL_SALARY = "Salary"
COL_COMPANY = "Company"
COL_COMPANY_SCORE = "Company Score"
COL_REMOTE = "Remote"
COL_CITY = "City"
COL_COUNTRY = "Country"

EXPERIENCE_KEYWORDS = {
    "0-1 years": ["entry", "entry-level", "junior", "graduate", "0-1", "fresh"],
    "1-2 years": ["1-2", "1 year", "2 years"],
    "2-3 years": ["2-3", "2+ years", "3 years"],
    "3-5 years": ["3-5", "3+ years", "4+ years", "5 years"],
    "5+ years": ["5+", "senior", "lead", "principal", "staff"]
}

# Numeric "floor" for each experience bucket, used only for ordering/comparison
# (e.g. is the user's years >= this bucket's floor). Keys MUST exactly match
# the bucket names produced by EXPERIENCE_KEYWORDS above.
EXPERIENCE_RANK = {
    "0-1 years": 0,
    "1-2 years": 1,
    "2-3 years": 2,
    "3-5 years": 3,
    "5+ years": 5,
    "Not specified": -1
}

# This dataset has no education info anywhere (no description, no dedicated
# field), so this will essentially always come back "Not specified"
# in case a future version of the dataset adds a description column
EDUCATION_KEYWORDS = {
    "Bachelor's Degree": ["bachelor", "bsc", "b.s", "b.a", "undergraduate"],
    "Master's Degree": ["masters", "master", "msc", "m.s", "m.a"],
    "PhD": ["phd"],
    "High School Diploma": ["high school", "secondary school", "diploma"]
}


def load_jobs_from_csv(filepath: str) -> List[Dict]:
    """Read job postings from a CSV file into a list of dicts (one per row)."""
    jobs = []
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                print(f"Error: Csv file {filepath} is empty or malformed")
                return []

            for row in reader:
                if not any(row.values()):
                    continue
                jobs.append(row)

            return jobs
    except FileNotFoundError:
        print(f"Error: file '{filepath}' not found")
        return []
    except Exception as e:
        print(f"Error reading file: {e}")
        return []


#Role search

def search_jobs_by_role(jobs: List[Dict], role_query: str) -> List[Dict]:
    """Return jobs whose title contains role_query (case-insensitive substring match)."""
    query_lower = role_query.strip().lower()
    if not query_lower:
        return []
    return [
        job for job in jobs
        if query_lower in job.get(COL_TITLE, '').lower()
    ]


#Skills analysis

def extract_skills(skills_field: str) -> List[str]:
    """Parse this dataset's 'Skills' column into a clean list."""
    if not skills_field:
        return []
    return [s.strip().lower() for s in skills_field.split(',') if s.strip()]


def analyze_skills(jobs: List[Dict]) -> Dict[str, float]:
    """Across all given jobs, compute what % of postings mention each skill."""
    all_skills = []

    for job in jobs:
        skills_field = job.get(COL_SKILLS, '')
        all_skills.extend(extract_skills(skills_field))

    if not all_skills or not jobs:
        return {}

    skill_counts = Counter(all_skills)
    total_jobs = len(jobs)

    return {
        skill: round((count / total_jobs) * 100, 1)
        for skill, count in skill_counts.most_common()
    }


def get_required_skills_for_role(jobs: List[Dict], role_query: str) -> Tuple[List[Dict], Dict[str, float]]:
    """Filter jobs down to a given role, then compute the skill breakdown for just those."""
    matches = search_jobs_by_role(jobs, role_query)
    skill_percentages = analyze_skills(matches)
    return matches, skill_percentages


#Experience analysis

def extract_experience_requirement(job_text: str) -> str:
    """Classify one job's text into an experience bucket based on keyword hits."""
    text_lower = job_text.lower()

    for category, keywords in EXPERIENCE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return category

    return "Not specified"


def analyze_experience(jobs: List[Dict]) -> Dict[str, float]:
    """Compute what % of jobs fall into each experience bucket."""
    experience_counts = Counter()
    for job in jobs:
        title_text = job.get(COL_TITLE, '')
        exp_level = extract_experience_requirement(title_text)
        experience_counts[exp_level] += 1

    total = sum(experience_counts.values())
    if total == 0:
        return {}

    return {
        exp: round((count / total) * 100, 1)
        for exp, count in experience_counts.most_common()
    }


def most_common_experience(jobs: List[Dict]) -> str:
    """Return whichever experience bucket has the highest percentage of jobs."""
    exp_breakdown = analyze_experience(jobs)
    if not exp_breakdown:
        return "Not specified"
    return max(exp_breakdown.items(), key=lambda item: item[1])[0]


#Education analysis 

def extract_education_requirement(job_text: str) -> str:
    """Classify one job's text into an education level."""
    text_lower = job_text.lower()

    for education_level, keywords in EDUCATION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return education_level

    return "Not specified"


def analyze_education(jobs: List[Dict]) -> Dict[str, float]:
    """Compute what % of jobs fall into each education level."""
    education_counts = Counter()

    for job in jobs:
        title_text = job.get(COL_TITLE, '')
        edu_level = extract_education_requirement(title_text)
        education_counts[edu_level] += 1

    total = sum(education_counts.values())
    if total == 0:
        return {}

    return {
        edu: round((count / total) * 100, 1)
        for edu, count in education_counts.most_common()
    }


def identify_common_qualifications(jobs: List[Dict], skill_threshold: float = 40.0) -> Dict:
    """Summarize a set of jobs: which skills are common (>= threshold%),
    and the single most typical experience/education level."""
    skills = analyze_skills(jobs)
    experience = analyze_experience(jobs)
    education = analyze_education(jobs)

    common_skills = [skill for skill, pct in skills.items() if pct >= skill_threshold]
    typical_experience = max(experience.items(), key=lambda i: i[1])[0] if experience else "Not specified"
    typical_education = max(education.items(), key=lambda i: i[1])[0] if education else "Not specified"

    return {
        'common_skills': common_skills,
        'typical_experience': typical_experience,
        'typical_education': typical_education
    }


#Salary analysis

def analyze_salary(jobs: List[Dict]) -> Dict:
    """Compute min/max/average/median salary across all jobs that have salary data."""
    salaries = []

    for job in jobs:
        try:
            raw = job.get(COL_SALARY)
            if raw and str(raw).strip():
                val = float(str(raw).replace(',', ''))
                if val > 0:
                    salaries.append(val)
        except (ValueError, TypeError):
            continue

    if not salaries:
        return {
            'minimum': 'N/A',
            'maximum': 'N/A',
            'average': 'N/A',
            'median': 'N/A',
            'jobs_with_salary': 0
        }

    salaries.sort()

    def format_salary(value: float) -> str:
        return f"£{int(value):,}"  # dataset is UK-based (GBP), not Naira

    median = (
        salaries[len(salaries) // 2]
        if len(salaries) % 2 == 1
        else (salaries[len(salaries) // 2 - 1] + salaries[len(salaries) // 2]) / 2
    )

    return {
        'minimum': format_salary(min(salaries)),
        'maximum': format_salary(max(salaries)),
        'average': format_salary(sum(salaries) / len(salaries)),
        'median': format_salary(median),
        'jobs_with_salary': len(salaries)
    }


#Skills-gap comparison (user vs role) 

def normalize_skill_list(raw_skills: List[str]) -> List[str]:
    """Clean up a user-provided skill list: trim whitespace, lowercase, drop blanks."""
    return [s.strip().lower() for s in raw_skills if s.strip()]


def compute_skills_gap(user_skills: List[str], required_skills: List[str]) -> Dict:
    """Compare what the user knows against what a role commonly requires."""
    user_set = set(normalize_skill_list(user_skills))
    required_set = set(s.lower() for s in required_skills)

    if not required_set:
        return {
            'matched_skills': [],
            'missing_skills': [],
            'match_percentage': 0.0,
            'gap_percentage': 0.0
        }

    matched = sorted(required_set & user_set)
    missing = sorted(required_set - user_set)

    match_pct = round((len(matched) / len(required_set)) * 100, 1)
    gap_pct = round(100 - match_pct, 1)

    return {
        'matched_skills': matched,
        'missing_skills': missing,
        'match_percentage': match_pct,
        'gap_percentage': gap_pct
    }


def compare_experience(user_years: float, required_level: str) -> str:
    """Turn a role's typical experience bucket + user's years into a plain-English verdict."""
    required_floor = EXPERIENCE_RANK.get(required_level, -1)

    if required_floor == -1:
        return "Role does not specify a clear experience requirement"

    if user_years >= required_floor + 2:
        return f"You exceed the typical requirement ({required_level})."
    elif user_years >= required_floor:
        return f"You meet the typical requirement ({required_level})."
    else:
        gap_years = required_floor - user_years
        return f"You are about {gap_years:.0f} year(s) short of the typical requirement ({required_level})."


def generate_personal_gap_report(jobs: List[Dict], role_query: str,
                                  user_skills: List[str], user_years: float,
                                  skill_threshold: float = 40.0) -> Dict:
    """Full pipeline: find postings for a role, then compare the user against them."""
    matches, skill_breakdown = get_required_skills_for_role(jobs, role_query)
    if not matches:
        return {'found': False, 'role_query': role_query}

    qualifications = identify_common_qualifications(matches, skill_threshold)
    salary = analyze_salary(matches)
    gap = compute_skills_gap(user_skills, qualifications['common_skills'])
    experience_verdict = compare_experience(user_years, qualifications['typical_experience'])

    return {
        'found': True,
        'role_query': role_query,
        'postings_matched': len(matches),
        'skill_breakdown': skill_breakdown,
        'common_skills': qualifications['common_skills'],
        'typical_experience': qualifications['typical_experience'],
        'typical_education': qualifications['typical_education'],
        'salary': salary,
        'skills_gap': gap,
        'experience_verdict': experience_verdict
    }


#Comparing two roles against each other 

def compare_roles(jobs: List[Dict], role_a: str, role_b: str,
                   skill_threshold: float = 40.0) -> Dict:
    """Compare the skill/experience/education/salary profile of two different roles."""
    matches_a, _ = get_required_skills_for_role(jobs, role_a)
    matches_b, _ = get_required_skills_for_role(jobs, role_b)

    if not matches_a or not matches_b:
        return {
            'found': False,
            'role_a': role_a,
            'role_b': role_b,
            'role_a_matches': len(matches_a),
            'role_b_matches': len(matches_b)
        }

    quals_a = identify_common_qualifications(matches_a, skill_threshold)
    quals_b = identify_common_qualifications(matches_b, skill_threshold)

    skills_a = set(quals_a['common_skills'])
    skills_b = set(quals_b['common_skills'])

    shared_skills = sorted(skills_a & skills_b)
    unique_to_a = sorted(skills_a - skills_b)
    unique_to_b = sorted(skills_b - skills_a)

    union_size = len(skills_a | skills_b)
    overlap_percentage = round((len(shared_skills) / union_size) * 100, 1) if union_size else 0.0

    salary_a = analyze_salary(matches_a)
    salary_b = analyze_salary(matches_b)

    return {
        'found': True,
        'role_a': role_a,
        'role_b': role_b,
        'postings_a': len(matches_a),
        'postings_b': len(matches_b),
        'shared_skills': shared_skills,
        'unique_to_a': unique_to_a,
        'unique_to_b': unique_to_b,
        'overlap_percentage': overlap_percentage,
        'typical_experience_a': quals_a['typical_experience'],
        'typical_experience_b': quals_b['typical_experience'],
        'typical_education_a': quals_a['typical_education'],
        'typical_education_b': quals_b['typical_education'],
        'salary_a': salary_a,
        'salary_b': salary_b
    }


#Display / reporting helpers

def print_header(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 50)
    print(f"  {title}")
    print("=" * 50)


def print_skills_report(skills: Dict[str, float], limit: int = 10):
    """Display top skills in a formatted table with a simple text bar chart."""
    print_header("Top Skills")

    if not skills:
        print("No skills data available")
        return

    top_skills = dict(list(skills.items())[:limit])
    max_skill_len = max(len(skill) for skill in top_skills.keys())

    for skill, percentage in top_skills.items():
        bar_length = int(percentage / 5)
        bar = "█" * bar_length
        print(f"{skill:<{max_skill_len}} {percentage:>5}% {bar}")


def print_experience_report(experience: Dict[str, float]):
    """Display experience requirements."""
    print_header("Experience Requirements")

    if not experience:
        print("No experience data available")
        return

    for exp_level, percentage in experience.items():
        print(f"{exp_level:<20} {percentage:>5}%")


def print_education_report(education: Dict[str, float]):
    """Display education requirements."""
    print_header("Education Requirements")

    if not education:
        print("No education data available")
        return

    for edu_level, percentage in education.items():
        print(f"{edu_level:<20} {percentage:>5}%")


def print_salary_report(salary_data: Dict):
    """Display salary analysis (min/max/avg/median + count of salary data points)."""
    print_header("Salary Analysis")

    if salary_data['minimum'] == 'N/A':
        print("No salary data available")
        return

    print(f"Minimum:     {salary_data['minimum']}")
    print(f"Maximum:     {salary_data['maximum']}")
    print(f"Average:     {salary_data['average']}")
    print(f"Median:      {salary_data['median']}")
    print(f"\nJobs with salary info: {salary_data['jobs_with_salary']}")


def print_role_search_report(role_query: str, matches: List[Dict], skill_breakdown: Dict[str, float]):
    """Display results of a role search: matched postings + their skill demand."""
    print_header(f"Role Search: '{role_query}'")

    if not matches:
        print(f"No postings found matching '{role_query}'")
        return

    print(f"Found {len(matches)} matching posting(s)\n")
    for job in matches[:5]:
        title = job.get(COL_TITLE, 'Unknown title')
        company = job.get(COL_COMPANY, 'Unknown company')
        city = job.get(COL_CITY, '')
        print(f"  - {title} @ {company} ({city})" if city else f"  - {title} @ {company}")
    if len(matches) > 5:
        print(f"  ... and {len(matches) - 5} more")

    print_skills_report(skill_breakdown)
    print_experience_report(analyze_experience(matches))
    print_education_report(analyze_education(matches))
    print_salary_report(analyze_salary(matches))


def print_personal_gap_report(report: Dict):
    """Display the personal skills-gap report against a target role."""
    print_header(f"SKILLS GAP REPORT: '{report.get('role_query', '')}'")

    if not report.get('found'):
        print(f"No postings found matching '{report.get('role_query', '')}'")
        return

    print(f"Postings analyzed: {report['postings_matched']}")
    print(f"Typical experience required: {report['typical_experience']}")
    print(f"Typical education required:  {report['typical_education']}\n")

    gap = report['skills_gap']
    print(f"Skill match:   {gap['match_percentage']}%")
    print(f"Skill gap:     {gap['gap_percentage']}%\n")

    if gap['matched_skills']:
        print("Skills you already have that match this role:")
        for skill in gap['matched_skills']:
            print(f"  ✓ {skill}")
    else:
        print("No overlap yet between your listed skills and this role's common skills.")

    print()
    if gap['missing_skills']:
        print("Skills to develop for this role:")
        for skill in gap['missing_skills']:
            print(f"  ✗ {skill}")
    else:
        print("You already cover every commonly required skill for this role!")

    print(f"\n{report['experience_verdict']}")
    print_salary_report(report['salary'])


def print_role_comparison_report(comparison: Dict):
    """Display a side-by-side comparison of two roles."""
    print_header(f"ROLE COMPARISON: '{comparison.get('role_a', '')}' vs '{comparison.get('role_b', '')}'")

    if not comparison.get('found'):
        print("Could not compare roles — one or both roles had no matching postings.")
        print(f"  '{comparison.get('role_a', '')}': {comparison.get('role_a_matches', 0)} posting(s)")
        print(f"  '{comparison.get('role_b', '')}': {comparison.get('role_b_matches', 0)} posting(s)")
        return

    print(f"Postings analyzed: {comparison['postings_a']} vs {comparison['postings_b']}")
    print(f"Skill overlap: {comparison['overlap_percentage']}%\n")

    print(f"Shared skills ({len(comparison['shared_skills'])}):")
    for skill in comparison['shared_skills']:
        print(f"  • {skill}")

    print(f"\nUnique to '{comparison['role_a']}' ({len(comparison['unique_to_a'])}):")
    for skill in comparison['unique_to_a']:
        print(f"  • {skill}")

    print(f"\nUnique to '{comparison['role_b']}' ({len(comparison['unique_to_b'])}):")
    for skill in comparison['unique_to_b']:
        print(f"  • {skill}")

    print(f"\nTypical experience — {comparison['role_a']}: {comparison['typical_experience_a']}")
    print(f"Typical experience — {comparison['role_b']}: {comparison['typical_experience_b']}")
    print(f"Typical education  — {comparison['role_a']}: {comparison['typical_education_a']}")
    print(f"Typical education  — {comparison['role_b']}: {comparison['typical_education_b']}")

    print(f"\n--- Salary: {comparison['role_a']} ---")
    print_salary_report(comparison['salary_a'])
    print(f"\n--- Salary: {comparison['role_b']} ---")
    print_salary_report(comparison['salary_b'])


#Interactive menu helpers

def prompt_user_skills() -> List[str]:
    """Ask the user for a comma-separated list of skills they have."""
    raw = input("Enter your skills, separated by commas: ")
    return [s.strip() for s in raw.split(",") if s.strip()]


def prompt_user_years() -> float:
    """Ask the user for their years of experience, defaulting to 0 on bad input."""
    raw = input("Enter your years of experience: ")
    try:
        return float(raw)
    except ValueError:
        print("Could not parse that as a number — defaulting to 0 years.")
        return 0.0


def run_role_search_flow(jobs: List[Dict]):
    """Interactive flow: search postings by role and show what's required."""
    role_query = input("Enter a role/job title to search for: ")
    matches, skill_breakdown = get_required_skills_for_role(jobs, role_query)
    print_role_search_report(role_query, matches, skill_breakdown)


def run_personal_gap_flow(jobs: List[Dict]):
    """Interactive flow: compare the user's own skills/experience to a role."""
    role_query = input("Enter a role/job title to check yourself against: ")
    user_skills = prompt_user_skills()
    user_years = prompt_user_years()
    report = generate_personal_gap_report(jobs, role_query, user_skills, user_years)
    print_personal_gap_report(report)


def run_role_comparison_flow(jobs: List[Dict]):
    """Interactive flow: compare two roles against each other."""
    role_a = input("Enter the first role/job title: ")
    role_b = input("Enter the second role/job title: ")
    comparison = compare_roles(jobs, role_a, role_b)
    print_role_comparison_report(comparison)


def run_full_market_overview(jobs: List[Dict]):
    """Run the original full-dataset overview (all postings, no filtering)."""
    skills = analyze_skills(jobs)
    experience = analyze_experience(jobs)
    education = analyze_education(jobs)
    salary = analyze_salary(jobs)

    print_skills_report(skills)
    print_experience_report(experience)
    print_education_report(education)
    print_salary_report(salary)


#Main entry point

def main():
    """Main entry point for JobScout."""

    print("\n" + "=" * 50)
    print("       Job Scout v2.1")
    print("   Job Market Intelligence Tool (CSV)")
    print("=" * 50)

    print(f"\nLoading jobs from {DATA_FILE}...")
    jobs = load_jobs_from_csv(DATA_FILE)

    if not jobs:
        print("No jobs loaded. Exiting.")
        return

    print(f"✓ Loaded {len(jobs)} job postings")

    while True:
        print("\n" + "-" * 50)
        print("MENU")
        print("-" * 50)
        print("1. Full market overview (all postings)")
        print("2. Search postings by role")
        print("3. Compare my skills/experience to a role")
        print("4. Compare two roles")
        print("5. Exit")

        choice = input("\nChoose an option (1-5): ").strip()

        if choice == "1":
            run_full_market_overview(jobs)
        elif choice == "2":
            run_role_search_flow(jobs)
        elif choice == "3":
            run_personal_gap_flow(jobs)
        elif choice == "4":
            run_role_comparison_flow(jobs)
        elif choice == "5":
            print("\nGoodbye!")
            break
        else:
            print("Invalid choice — please enter a number from 1 to 5.")

    print("\n" + "=" * 50)
    print("Session complete!")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()