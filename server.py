import os
import re
import json
import hmac
import hashlib
import secrets
import sqlite3
import mimetypes
import smtplib
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps
from html import escape
from uuid import uuid4

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, send_file, url_for
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
# Some deployments keep the environment file in the extracted `revled` folder.
load_dotenv(os.path.join(BASE_DIR, "revled", ".env"), override=False)

RUNTIME_DEFAULTS = {
    "SECRET_KEY": "change-me",
    "REVLED_ADMIN_EMAIL": "",
    "REVLED_ADMIN_PASSWORD": "",
    "REVLED_EMAIL_USERNAME": "info@revledfoundation.org",
    "REVLED_EMAIL_PASSWORD": "",
    "REVLED_EMAIL_INCOMING_SERVER": "revledfoundation.org",
    "REVLED_EMAIL_SMTP_SERVER": "revledfoundation.org",
    "REVLED_EMAIL_SMTP_PORT": "465",
    "REVLED_EMAIL_USE_SSL": "1",
    "REVLED_EMAIL_TIMEOUT": "20",
    "REVLED_SITE_URL": "https://revledfoundation.org",
    "PAYSTACK_SECRET_KEY": "",
    "PAYSTACK_PUBLIC_KEY": "",
}

app.secret_key = os.environ.get("SECRET_KEY", RUNTIME_DEFAULTS["SECRET_KEY"])

DATABASE_PATH = os.path.join(BASE_DIR, "revled.db")
DEFAULT_ADMIN_EMAIL = os.environ.get("REVLED_ADMIN_EMAIL", RUNTIME_DEFAULTS["REVLED_ADMIN_EMAIL"]).strip().lower()
DEFAULT_ADMIN_PASSWORD = os.environ.get("REVLED_ADMIN_PASSWORD", RUNTIME_DEFAULTS["REVLED_ADMIN_PASSWORD"])

# Add after creating the Flask app
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Create a custom template loader with UTF-8
from jinja2 import FileSystemLoader, TemplateNotFound

class UTF8FileSystemLoader(FileSystemLoader):
    def get_source(self, environment, template):
        for searchpath in self.searchpath:
            filename = os.path.join(searchpath, template)
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    source = f.read()
                    return source, filename, lambda: False
        raise TemplateNotFound(template)

# Replace the default loader
app.jinja_loader = UTF8FileSystemLoader('templates')
RESOURCE_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "resources")
BLOG_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "blog")
HUB_UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "hub_private")
ALLOWED_RESOURCE_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "zip", "png", "jpg", "jpeg", "mp4", "webm", "mov"}
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
LOGO_PATH = "images/logo.png"
GOODSTACK_LOGO_PATH = "images/goodstack-logo.svg"
REVLED_EMAIL_USERNAME = RUNTIME_DEFAULTS["REVLED_EMAIL_USERNAME"]
REVLED_EMAIL_PASSWORD = RUNTIME_DEFAULTS["REVLED_EMAIL_PASSWORD"]
REVLED_EMAIL_INCOMING_SERVER = RUNTIME_DEFAULTS["REVLED_EMAIL_INCOMING_SERVER"]
REVLED_EMAIL_SMTP_SERVER = RUNTIME_DEFAULTS["REVLED_EMAIL_SMTP_SERVER"]
REVLED_EMAIL_SMTP_PORT = int(RUNTIME_DEFAULTS["REVLED_EMAIL_SMTP_PORT"])
REVLED_EMAIL_USE_SSL = RUNTIME_DEFAULTS["REVLED_EMAIL_USE_SSL"] != "0"
REVLED_EMAIL_TIMEOUT = int(RUNTIME_DEFAULTS["REVLED_EMAIL_TIMEOUT"])
VOLUNTEERS_EMAIL = os.environ.get(
    "REVLED_VOLUNTEERS_EMAIL",
    "volunteers@revledfoundation.org",
).strip().lower()
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", RUNTIME_DEFAULTS["PAYSTACK_SECRET_KEY"]).strip()
PAYSTACK_PUBLIC_KEY = os.environ.get("PAYSTACK_PUBLIC_KEY", RUNTIME_DEFAULTS["PAYSTACK_PUBLIC_KEY"]).strip()
REVLED_SITE_URL = os.environ.get("REVLED_SITE_URL", RUNTIME_DEFAULTS["REVLED_SITE_URL"]).strip()
CAC_REGISTRATION_NUMBER = "164929"
NONPROFIT_LEGAL_NAME = "Revled Empowerment Initiative"
OPERATING_NAME = "Revled Foundation"
SITE_LAST_UPDATED = datetime.utcnow().strftime("%B %d, %Y").replace(" 0", " ")
SITE_TRANSPARENCY_SUMMARY = ""
SITE_COUNTERS = {
    "home": {
        "young_minds_reached": 0,
        "workshops_delivered": 0,
        "schools_engaged": 0,
        "internship_placements": 0,
    },
    "impact": {
        "lives_impacted": 0,
        "communities": 0,
        "mentors_trained": 0,
        "success_rate": 0,
    },
}
HUB_USER_TYPES = {
    "ENTREPRENEUR": "Entrepreneur",
    "PROFESSIONAL": "Professional",
}

# Path to the welcome kit PDF (can be overridden via env var)
WELCOME_KIT_PATH = os.environ.get(
    "WELCOME_KIT_PATH",
    os.path.join(HUB_UPLOAD_DIR, "Revled_Vanguard_Welcome_Kit-1.pdf"),
)

CONTACT_DIRECTORY = {
    "leadership": [
        {"label": "CEO", "email": "ceo@revledfoundation.org"},
        {"label": "Founder", "email": "chidimma.azike@revledfoundation.org"},
        {"label": "General Information", "email": "info@revledfoundation.org"},
        {"label": "Board", "email": "board@revledfoundation.org"},
    ],
    "operations": [
        {"label": "Partnerships", "email": "partnerships@revledfoundation.org"},
        {"label": "Donations", "email": "donations@revledfoundation.org"},
        {"label": "Finance", "email": "finance@revledfoundation.org"},
        {"label": "Legal", "email": "legal@revledfoundation.org"},
        {"label": "Volunteers", "email": "volunteers@revledfoundation.org"},
        {"label": "Press", "email": "press@revledfoundation.org"},
        {"label": "Events", "email": "events@revledfoundation.org"},
        {"label": "Newsletter", "email": "newsletter@revledfoundation.org"},
    ],
    "programmes": {
        "roots": {"label": "Revled Origin", "email": "origin@revledfoundation.org"},
        "explorers": {"label": "Revled Explorers", "email": "explorers@revledfoundation.org"},
        "catalyst": {"label": "Revled Catalyst", "email": "catalyst@revledfoundation.org"},
        "launchpad": {"label": "Revled Vanguard", "email": "vanguard@revledfoundation.org"},
    },
}

FAQ_SECTIONS = [
    {
        "title": "About the Foundation",
        "questions": [
            {
                "question": "What is your mission?",
                "answer": "To equip children and young people, particularly those from underserved communities, with the emotional intelligence, practical skills, mentorship, career readiness, and leadership capabilities they need to thrive while creating resilient, inclusive, and sustainable communities.",
            },
            {
                "question": "What is your vision?",
                "answer": "A world where every child and young person has the opportunity to realise their full potential, lead purposeful lives, and build thriving, inclusive, and sustainable communities.",
            },
            {
                "question": "Who do you serve?",
                "answer": "Children and young people in Nigeria across four life stages: ages 0–8 (Origin), 9–13 (Explorers), 14–18 (Catalyst), and 19–25 (Vanguard).",
            },
            {
                "question": "Where do you operate?",
                "answer": "Lagos, Nigeria.",
            },
        ],
    },
    {
        "title": "Programs & Training",
        "questions": [
            {
                "question": "What is RE-CREATE?",
                "answer": "Every Revled programme is designed using our Learn–Create–Innovate–Transform–Thrive approach, ensuring participants gain the skills, confidence, and opportunities to build meaningful futures while making a positive impact in their communities. Connect → Reimagine → Equip → Apply → Transform → Elevate.",
            },
            {
                "question": "What skills do you teach?",
                "answer": "Graphic Design, Digital Marketing, Entrepreneurship, and Communication & Leadership delivered through the Catalyst programme for ages 13–18 with our signature Earn - Learn - Grow system.",
            },
            {
                "question": "How long are the programmes?",
                "answer": "Programmes run in cohort format with clear start and end dates.",
            },
            {
                "question": "Is there a cost to participate?",
                "answer": "Yes, however, scholarships are usually available through the help of sponsors and grants received. Individuals or organisations can sponsor a young person to participate.",
            },
            {
                "question": "What age range do you serve?",
                "answer": "Ages 0 to 25, across four structured programmes.",
            },
            {
                "question": "How do I enrol?",
                "answer": "You can apply directly through the programme pages.",
            },
        ],
    },
    {
        "title": "Support & Partnerships",
        "questions": [
            {
                "question": "How can I donate or sponsor?",
                "answer": "Visit the partnership page or contact donations@revledfoundation.org for donations and partnerships@revledfoundation.org for sponsorship enquiries.",
            },
            {
                "question": "Can my company partner or sponsor a cohort?",
                "answer": "Yes, there is a dedicated sponsor enquiry page on the website, or you can send an email to partnerships@revledfoundation.org.",
            },
            {
                "question": "Do you accept volunteers or mentors?",
                "answer": "Yes, through the Partner page on the website, or by emailing volunteers@revledfoundation.org.",
            },
        ],
    },
    {
        "title": "Outcomes",
        "questions": [
            {
                "question": "What happens after training?",
                "answer": "Participants move through the Revled journey; Catalyst graduates progress toward Vanguard, which focuses on professional incubation and job placement.",
            },
            {
                "question": "Do you help with job placement?",
                "answer": "Yes, through the Vanguard programme for ages 19–25.",
            },
        ],
    },
]

PROGRAMS = {
    "roots": {
        "slug": "roots",
        "name": "Revled Origin",
        "ages": "Ages 0-8",
        "tone": "Play, bond, and discover the foundations for every future step.",
        "cta": "Enroll your child into the Origin journey.",
        "accent": "emerald",
        "tagline": "Where every journey begins",
        "hero_headline": "Where Every Child's Story Begins.",
        "hero_subheadline": "Before a child can Connect, Reimagine, or Create, they need to Play, Bond, and Discover. Origin lays that foundation, building the emotional security and curiosity every child needs for what comes next.",
        "primary_cta_label": "Watch Free Videos",
        "primary_cta_type": "youtube",
        "primary_cta_anchor": "videos",
        "secondary_cta_label": "Little Learners",
        "secondary_cta_type": "resources",
        "secondary_cta_anchor": "storybooks",
        "intro_heading": "Warm, playful, and trustworthy by design.",
        "intro_body": "Revled Origin is built for parents who want more than random screen time. It gives children aged 0-8 the emotional security, curiosity, and joyful learning experiences they need to move confidently into the rest of the Revled journey.",
        "audience_note": "This page speaks directly to parents of children aged 0 to 8 who want safe, high-quality, Nigerian-centred content.",
        "outcomes_heading": "What Your Child Will Learn",
        "outcomes": [
            {"title": "English & Literacy", "desc": "Building reading confidence and love of language through storytelling."},
            {"title": "Maths & Numeracy", "desc": "Early number sense through play-based, animated learning."},
            {"title": "Moral Values", "desc": "Kindness, respect, and discipline taught through African-centred stories."},
            {"title": "Emotional Intelligence", "desc": "Helping children recognise and express their feelings from an early age."},
        ],
        "framework_heading": "Play · Bond · Discover",
        "framework_points": [
            "The foundation for everything they'll Connect, Reimagine, and Create later in their Revled journey.",
        ],
        "fee_note": "Free video library. Storybooks and printable packs can be purchased separately.",
        "location_note": "Access online from anywhere in the world, with periodic school and community activations.",
        "extra_section_heading": "Take the Learning Offline",
        "extra_section_body": "Storybooks, colouring books, and activity packs are designed to reinforce the same lessons children see in our videos so the learning continues when the screen is off.",
        "business_note": "Origin helps children build the emotional and learning foundations that support every stage of life that follows.",
        "business_ctas": [
            {"label": "Subscribe on YouTube", "url_type": "youtube"},
            {"label": "Get Free Parent Resources", "url_type": "resources", "anchor": "guides"},
        ],
        "school_cta": {"label": "For Schools", "url_type": "enquiry", "enquiry_type": "school-partnership"},
        "show_workbooks": True,
        "event_heading": "Recommended learning sessions",
    },
    "explorers": {
        "slug": "explorers",
        "name": "Revled Explorers",
        "ages": "Ages 9-14",
        "tone": "Discovering who they are and what they can create.",
        "cta": "Help your child discover their gifts with Explorers.",
        "accent": "blue",
        "tagline": "The RE-CREATE Framework",
        "hero_headline": "The Years That Shape Who They Become.",
        "hero_subheadline": "Every learner's journey starts with looking inward and choosing to grow. Revled Explorers gives children the emotional intelligence, mentorship, and practical learning they need to discover who they are and what they can create.",
        "primary_cta_label": "Bring this to your school",
        "primary_cta_type": "register",
        "secondary_cta_label": "Enquire about explorers",
        "secondary_cta_type": "enquiry",
        "secondary_enquiry_type": "school-partnership",
        "intro_heading": "Not tutoring. Not vague motivation. Structured development.",
        "intro_body": "Revled Explorers is a 6 to 8-week term programme delivered in small cohorts, in schools or as an after-school experience. It helps children build self-awareness, confidence, creativity, and responsibility at the stage where identity is beginning to form.",
        "audience_note": "This page is built for parents and school administrators making a deliberate decision about character and life-skills development.",
        "outcomes_heading": "What Your Child Will Gain",
        "outcomes": [
            {"title": "Confidence", "desc": "They will learn to speak in front of others, articulate their ideas, and back themselves in new situations."},
            {"title": "Self-Awareness", "desc": "They will understand their strengths, manage their emotions, and make better decisions under pressure."},
            {"title": "Creativity & Expression", "desc": "Through writing, art, and challenges, they will discover what they are genuinely good at."},
            {"title": "Responsibility", "desc": "They will complete a real project, take ownership, and experience what it feels like to deliver."},
        ],
        "framework_heading": "RE — Reduce • C — Connect • R — Reimagine • E — Equip • A — Apply • T — Transform • E — Elevate",
        "framework_points": [
            "C — Connect — Emotional Intelligence & Mentorship",
            "R — Reimagine — Creativity & Problem Solving",
            "E — Equip — Practical & Career Skills",
            "A — Apply — Real-world Projects & Enterprise",
            "T — Transform — Community Impact",
            "E — Elevate — Leadership & Growth",
        ],
        "fee_note": "Fees vary by cohort, term length, and location. Sponsored places are available for some schools.",
        "location_note": "Delivered in schools, partner centres, and selected after-school hubs.",
        "extra_section_heading": "Bring Revled Explorers to Your School",
        "extra_section_body": "We work directly with primary and junior secondary schools to deliver Revled Explorers as part of the enrichment calendar. Revled handles facilitation, materials, and reporting while your school provides space and student coordination.",
        "through_recreate": "Through ReCreate, we encourage participants to see value where others see waste. By repurposing donated technology, fabrics, furniture, and other materials into learning tools, marketable products, and community assets, participants develop practical skills while contributing to cleaner, stronger, and more resourceful communities.",
        "business_note": "Explorers helps learners discover who they are while learning how to turn curiosity into confidence.",
        "business_ctas": [
            {"label": "Request a School Proposal", "url_type": "enquiry", "enquiry_type": "school-partnership"},
            {"label": "Sponsor a Cohort", "url_type": "enquiry", "enquiry_type": "sponsor-cohort"},
        ],
        "school_cta": {"label": "Request a School Proposal", "url_type": "enquiry", "enquiry_type": "school-partnership"},
        "show_workbooks": True,
        "event_heading": "Upcoming cohorts and holiday bootcamps",
    },
    "catalyst": {
        "slug": "catalyst",
        "name": "Revled Catalyst",
        "ages": "Ages 14-17",
        "tone": "Purposeful, practical, and built around output.",
        "cta": "Register for the Catalyst experience.",
        "accent": "orange",
        "tagline": "The RE-CREATE Framework",
        "hero_headline": "Purposeful, practical, and built around output.",
        "hero_subheadline": "This is Revled's most operationally proven tier. It is designed for teenagers who are bored with theory, parents who want direction, and sponsors who want a credible youth skills programme to back.",
        "primary_cta_label": "Sponsor a young person",
        "primary_cta_type": "register",
        "secondary_cta_label": "Enquire about Catalyst",
        "secondary_cta_type": "enquiry",
        "secondary_enquiry_type": "sponsor-cohort",
        "intro_heading": "What Catalyst Learners Build",
        "intro_body": "Catalyst is where practical skills become visible outcomes. Learners work through creative, commercial, and communication challenges that build confidence, competence, and proof of growth.",
        "audience_note": "Catalyst speaks to parents, teenagers, and sponsors at the same time, but it leads with practical outcomes and proof.",
        "outcomes_heading": "What Skills Are Taught",
        "outcomes": [
            {"title": "Graphic Design", "desc": "Logo creation, poster design, and basic branding using Canva and design fundamentals."},
            {"title": "Digital Marketing", "desc": "Content strategy, copywriting, analytics basics, and a live mini-campaign."},
            {"title": "Entrepreneurship", "desc": "Business idea validation, simple finance, pitching, and Revled's Learn → Do → Earn model."},
            {"title": "Communication & Leadership", "desc": "Public speaking, negotiation, group project management, and professional presentation."},
        ],
        "framework_heading": "RE — Reduce • C — Connect • R — Reimagine • E — Equip • A — Apply • T — Transform • E — Elevate",
        "framework_points": [
            "RE — Reduce, Reuse, Recycle, Repurpose. Every learner's journey starts with looking inward and choosing to grow.",
            "C — Connect — Emotional Intelligence & Mentorship",
            "R — Reimagine — Creativity & Problem Solving",
            "E — Equip — Practical & Career Skills",
            "A — Apply — Real-world Projects & Enterprise",
            "T — Transform — Community Impact",
            "E — Elevate — Leadership & Growth",
        ],
        "fee_note": "Paid enrolment with sponsor-subsidised seats available in qualifying cohorts.",
        "location_note": "Runs in cohort format with clear dates, locations, facilitators, and project output.",
        "extra_section_heading": "Help a Young Nigerian Build a Skill",
        "extra_section_body": "Corporate sponsors and grant partners can fund the training, materials, facilitation, and reporting for a Catalyst cohort. Sponsors receive impact visibility, reporting, and association with verified skills outcomes.",
        "through_recreate": "Through ReCreate, we encourage participants to see value where others see waste. By repurposing donated technology, fabrics, furniture, and other materials into learning tools, marketable products, and community assets, participants develop practical skills while contributing to cleaner, stronger, and more resourceful communities.",
        "business_note": "Catalyst turns curiosity into tangible skills, projects, and leadership experiences that matter.",
        "business_ctas": [
            {"label": "Sponsor a Cohort", "url_type": "enquiry", "enquiry_type": "sponsor-cohort"},
            {"label": "Contact Us About Sponsoring", "url_type": "contact", "anchor": ""},
        ],
        "school_cta": {"label": "Talk to Revled", "url_type": "contact", "anchor": ""},
        "show_workbooks": False,
        "event_heading": "Next Catalyst cohorts and public bootcamps",
    },
    "launchpad": {
        "slug": "launchpad",
        "name": "Revled Vanguard",
        "ages": "Ages 18-25",
        "tone": "From equipped to employed; leading with purpose.",
        "cta": "Apply to join the Vanguard track.",
        "accent": "purple",
        "tagline": "The RE-CREATE Framework",
        "hero_headline": "The Gap Between Where You Are and Where You Want to Be Is Smaller Than You Think.",
        "hero_subheadline": "RE — Reduce, Reuse, Recycle, Repurpose. Every learner's journey starts with looking inward and choosing to grow. Vanguard helps young people move from equipped to employed while building communities that thrive.",
        "primary_cta_label": "Join for Free",
        "primary_cta_type": "register",
        "primary_enquiry_type": "join-launchpad",
        "secondary_cta_label": "Enquire about Vanguard",
        "secondary_cta_type": "vanguard",
        "intro_heading": "Clear access. Practical support. Real momentum.",
        "intro_body": "Vanguard is built for ambitious young adults who want a direct route into opportunity. It starts with free access and grows into deeper support for internships, short skills tracks, and career direction.",
        "audience_note": "This page speaks to smart young Nigerians aged 18 to 25 who want real access, not motivational talk.",
        "outcomes_heading": "Every programme contributes to",
        "contribution_points": [
            "Future-ready skills",
            "Leadership development",
            "Enterprise & employability",
            "Community impact",
            "Sustainable thinking",
        ],
        "framework_heading": "RE — Reduce • C — Connect • R — Reimagine • E — Equip • A — Apply • T — Transform • E — Elevate",
        "framework_points": [
            "RE — Reduce, Reuse, Recycle, Repurpose. Every learner's journey starts with looking inward and choosing to grow.",
            "C — Connect — Emotional Intelligence & Mentorship",
            "R — Reimagine — Creativity & Problem Solving",
            "E — Equip — Practical & Career Skills",
            "A — Apply — Real-world Projects & Enterprise",
            "T — Transform — Community Impact",
            "E — Elevate — Leadership & Growth",
        ],
        "fee_note": "Free entry now, with a clear low-cost upgrade path for deeper support.",
        "location_note": "Digital-first community with selective in-person bootcamps and industry sessions.",
        "extra_section_heading": "We Don't Just Talk About Opportunities. We Open Them.",
        "extra_section_body": "Vanguard connects members to industry conversations, internship access, and targeted career tracks built around real barriers young people face when entering work.",
        "through_recreate": "Through ReCreate, we encourage participants to see value where others see waste. By repurposing donated technology, fabrics, furniture, and other materials into learning tools, marketable products, and community assets, participants develop practical skills while contributing to cleaner, stronger, and more resourceful communities.",
        "business_note": "Vanguard equips young adults to move confidently from learning into work, leadership, and enterprise.",
        "business_ctas": [
            {"label": "Join Free Now", "url_type": "vanguard"},
            {"label": "Book a Career Consultation", "url_type": "consultation", "anchor": ""},
        ],
        "school_cta": {"label": "See Membership Plans", "url_type": "vanguard"},
        "show_workbooks": False,
        "event_heading": "Industry conversations and skills bootcamps",
    },
}

HUB_CONTENT_TYPES = {
    "schedule": {
        "label": "Schedule",
        "singular": "session",
        "icon": "fa-calendar-alt",
        "description": "Live classes, workshops, and upcoming hub sessions.",
        "empty_message": "No schedule items have been published yet.",
        "meta_one_label": "Speaker / host",
        "meta_two_label": "Session format",
        "default_cta": "View session",
    },
    "resources": {
        "label": "Resources",
        "singular": "resource",
        "icon": "fa-folder-open",
        "description": "Templates, videos, guides, and practical tools for members.",
        "empty_message": "No hub resources have been published yet.",
        "meta_one_label": "Resource type",
        "meta_two_label": "Access note",
        "default_cta": "Open resource",
    },
    "community": {
        "label": "Community",
        "singular": "community space",
        "icon": "fa-users",
        "description": "Discussion rooms, peer circles, accountability spaces, and live rooms.",
        "empty_message": "No community spaces have been published yet.",
        "meta_one_label": "Host / lead",
        "meta_two_label": "Member note",
        "default_cta": "Join space",
    },
    "opportunities": {
        "label": "Opportunities",
        "singular": "opportunity",
        "icon": "fa-briefcase",
        "description": "Jobs, internships, fellowships, and open calls curated for hub members.",
        "empty_message": "No opportunities have been published yet.",
        "meta_one_label": "Company / organizer",
        "meta_two_label": "Role type",
        "default_cta": "Open opportunity",
    },
    "challenges": {
        "label": "Challenges",
        "singular": "challenge",
        "icon": "fa-trophy",
        "description": "Practical milestones and assignments that keep members moving forward.",
        "empty_message": "No challenges have been published yet.",
        "meta_one_label": "Difficulty / owner",
        "meta_two_label": "Outcome",
        "default_cta": "View challenge",
    },
}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def timestamp():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password):
    return generate_password_hash(password, method="pbkdf2:sha256")


def slugify(value):
    value = re.sub(r"[^a-zA-Z0-9\s-]", "", value).strip().lower()
    value = re.sub(r"[\s_-]+", "-", value)
    return value or f"item-{int(datetime.utcnow().timestamp())}"


def fetch_one(query, params=()):
    return get_db().execute(query, params).fetchone()


def fetch_all(query, params=()):
    return get_db().execute(query, params).fetchall()


def execute(query, params=()):
    db = get_db()
    cursor = db.execute(query, params)
    db.commit()
    return cursor


def create_admin_notification(category, title, summary, source_table="", source_id=None):
    execute(
        """
        INSERT INTO admin_notifications (category, title, summary, source_table, source_id, is_read, created_at)
        VALUES (?, ?, ?, ?, ?, 0, ?)
        """,
        (category, title, summary, source_table, source_id, timestamp()),
    )


def record_vanguard_mentor_application(form_data):
    full_name = (form_data.get("full_name") or "").strip()
    email = (form_data.get("email") or "").strip().lower()
    phone = (form_data.get("phone") or "").strip()
    current_role_org = (form_data.get("current_role_org") or "").strip()
    industry = (form_data.get("industry") or "").strip()
    other_industry = (form_data.get("other_industry") or "").strip()
    availability = form_data.get("availability") or []
    if isinstance(availability, str):
        availability = [availability]
    availability_text = ", ".join(str(item).strip() for item in availability if str(item).strip())
    frequency = (form_data.get("frequency") or "").strip()
    availability_notes = (form_data.get("availability_notes") or "").strip()
    topics = (form_data.get("topics") or "").strip()

    if not full_name or not email or not current_role_org or not industry or not frequency:
        raise ValueError("Please complete the required mentor details before submitting.")

    if industry == "Other":
        industry = other_industry or "Other"

    now = timestamp()
    cursor = execute(
        """
        INSERT INTO vanguard_mentor_applications (
            full_name, email, phone, current_role_org, industry, other_industry,
            availability, frequency, availability_notes, topics, status, admin_notes,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', '', ?, ?)
        """,
        (
            full_name,
            email,
            phone,
            current_role_org,
            industry,
            other_industry,
            availability_text,
            frequency,
            availability_notes,
            topics,
            now,
            now,
        ),
    )
    create_admin_notification(
        "mentor-signup",
        "New mentor signup",
        f"{full_name} submitted a mentor application.",
        "vanguard_mentor_applications",
        cursor.lastrowid,
    )
    return True


def record_catalyst_application(form_data):
    full_name = (form_data.get("full_name") or "").strip()
    email = (form_data.get("email") or "").strip().lower()
    phone = (form_data.get("phone") or "").strip()
    current_role_org = (form_data.get("current_role_org") or "").strip()
    involvement_type = (form_data.get("involvement_type") or "").strip()
    skill_area = (form_data.get("skill_area") or "").strip()
    other_skill = (form_data.get("other_skill") or "").strip()
    availability = form_data.get("availability") or []
    if isinstance(availability, str):
        availability = [availability]
    availability_text = ", ".join(str(item).strip() for item in availability if str(item).strip())
    availability_notes = (form_data.get("availability_notes") or "").strip()
    additional_notes = (form_data.get("additional_notes") or "").strip()

    if not full_name or not email or not involvement_type or not skill_area:
        raise ValueError("Please complete the required Catalyst application details before submitting.")

    if skill_area == "Other":
        skill_area = other_skill or "Other"

    now = timestamp()
    cursor = execute(
        """
        INSERT INTO catalyst_applications (
            full_name, email, phone, current_role_org, involvement_type, skill_area,
            other_skill, availability, availability_notes, additional_notes,
            status, admin_notes, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', '', ?, ?)
        """,
        (
            full_name,
            email,
            phone,
            current_role_org,
            involvement_type,
            skill_area,
            other_skill,
            availability_text,
            availability_notes,
            additional_notes,
            now,
            now,
        ),
    )
    create_admin_notification(
        "catalyst-application",
        "New Catalyst volunteer application",
        f"{full_name} submitted a Catalyst volunteer or mentor application.",
        "catalyst_applications",
        cursor.lastrowid,
    )
    return True


def ensure_directory(path):
    os.makedirs(path, exist_ok=True)


def ensure_column(db, table_name, column_name, definition):
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if column_name not in columns:
        db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def allowed_resource_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_RESOURCE_EXTENSIONS


def allowed_image_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def save_resource_file(upload):
    if not upload or not upload.filename:
        return None
    if not allowed_resource_file(upload.filename):
        return None
    ensure_directory(RESOURCE_UPLOAD_DIR)
    original = secure_filename(upload.filename)
    unique_name = f"{uuid4().hex}_{original}"
    upload.save(os.path.join(RESOURCE_UPLOAD_DIR, unique_name))
    return unique_name


def save_hub_file(upload):
    if not upload or not upload.filename:
        return None
    if not allowed_resource_file(upload.filename):
        return None
    ensure_directory(HUB_UPLOAD_DIR)
    original = secure_filename(upload.filename)
    unique_name = f"{uuid4().hex}_{original}"
    upload.save(os.path.join(HUB_UPLOAD_DIR, unique_name))
    return {"stored_name": unique_name, "original_name": original}


def save_public_image_file(upload, upload_dir, url_prefix):
    if not upload or not upload.filename:
        return None
    if not allowed_image_file(upload.filename):
        return None
    ensure_directory(upload_dir)
    original = secure_filename(upload.filename)
    unique_name = f"{uuid4().hex}_{original}"
    upload.save(os.path.join(upload_dir, unique_name))
    return f"{url_prefix}/{unique_name}"


def send_email_message(recipient, subject, plain_text, html_text=None):
    username = resolve_runtime_value("REVLED_EMAIL_USERNAME", REVLED_EMAIL_USERNAME)
    password = resolve_runtime_value("REVLED_EMAIL_PASSWORD", REVLED_EMAIL_PASSWORD)
    smtp_server = resolve_runtime_value("REVLED_EMAIL_SMTP_SERVER", REVLED_EMAIL_SMTP_SERVER)
    smtp_port = int(resolve_runtime_value("REVLED_EMAIL_SMTP_PORT", str(REVLED_EMAIL_SMTP_PORT)))
    use_ssl = resolve_runtime_value("REVLED_EMAIL_USE_SSL", "1" if REVLED_EMAIL_USE_SSL else "0") != "0"
    timeout = int(resolve_runtime_value("REVLED_EMAIL_TIMEOUT", str(REVLED_EMAIL_TIMEOUT)))
    if not password:
        raise RuntimeError("REVLED_EMAIL_PASSWORD is not configured.")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = username
    message["To"] = recipient
    message.set_content(plain_text)
    if html_text:
        message.add_alternative(html_text, subtype="html")
    if use_ssl:
        with smtplib.SMTP_SSL(
            smtp_server,
            smtp_port,
            timeout=timeout,
        ) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(
            smtp_server,
            smtp_port,
            timeout=timeout,
        ) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(message)


def send_registration_confirmation_email(full_name, email, program_name):
    login_name = escape(full_name)
    plain_text = (
        f"Hello {full_name},\n\n"
        f"Your registration for {program_name} has been received.\n\n"
        "The Revled team will review your details and follow up with you soon.\n\n"
        "Warmly,\nThe Revled Foundation Team"
    )
    html_text = (
        f"<p>Hello {login_name},</p>"
        f"<p>Your registration for <strong>{escape(program_name)}</strong> has been received.</p>"
        "<p>The Revled team will review your details and follow up with you soon.</p>"
        "<p>Warmly,<br>The Revled Foundation Team</p>"
    )
    send_email_message(
        email,
        f"Registration received: {program_name}",
        plain_text,
        html_text=html_text,
    )


def send_volunteer_submission_email(program_name, form_data):
    details = []
    for label, key in (
        ("Full name", "full_name"),
        ("Email", "email"),
        ("Phone", "phone"),
        ("Current role / organisation", "current_role_org"),
        ("Industry", "industry"),
        ("Involvement type", "involvement_type"),
        ("Skill area", "skill_area"),
        ("Other industry", "other_industry"),
        ("Other skill", "other_skill"),
        ("Availability", "availability"),
        ("Frequency", "frequency"),
        ("Availability notes", "availability_notes"),
        ("Topics", "topics"),
        ("Additional notes", "additional_notes"),
    ):
        value = form_data.get(key, "")
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value if item)
        if value:
            details.append(f"{label}: {value}")
    plain_text = (
        f"A new {program_name} volunteer or mentor application was submitted.\n\n"
        + "\n".join(details)
    )
    html_details = "".join(
        f"<li><strong>{escape(label)}:</strong> {escape(str(value))}</li>"
        for label, key in (
            ("Full name", "full_name"),
            ("Email", "email"),
            ("Phone", "phone"),
            ("Current role / organisation", "current_role_org"),
            ("Industry", "industry"),
            ("Involvement type", "involvement_type"),
            ("Skill area", "skill_area"),
            ("Other industry", "other_industry"),
            ("Other skill", "other_skill"),
            ("Availability", "availability"),
            ("Frequency", "frequency"),
            ("Availability notes", "availability_notes"),
            ("Topics", "topics"),
            ("Additional notes", "additional_notes"),
        )
        for value in [form_data.get(key, "")]
        if value
    )
    html_text = (
        f"<p>A new <strong>{escape(program_name)}</strong> volunteer or mentor application was submitted.</p>"
        f"<ul>{html_details}</ul>"
    )
    send_email_message(
        VOLUNTEERS_EMAIL,
        f"New {program_name} volunteer application",
        plain_text,
        html_text=html_text,
    )


def current_date_label():
    return datetime.utcnow().strftime("%B %d, %Y").replace(" 0", " ")


def build_absolute_url(path):
    base_url = REVLED_SITE_URL or request.url_root.rstrip("/")
    if not base_url:
        return path
    if path.startswith("/"):
        return f"{base_url}{path}"
    return f"{base_url}/{path}"


def get_paystack_secret_key():
    return resolve_runtime_value("PAYSTACK_SECRET_KEY", "").strip()


def get_paystack_public_key():
    return resolve_runtime_value("PAYSTACK_PUBLIC_KEY", "").strip()


def get_site_base_url():
    return resolve_runtime_value("REVLED_SITE_URL", RUNTIME_DEFAULTS["REVLED_SITE_URL"]).strip().rstrip("/")


def paystack_request(method, endpoint, payload=None):
    secret_key = get_paystack_secret_key()
    if not secret_key:
        raise RuntimeError("PAYSTACK_SECRET_KEY is not configured.")
    url = f"https://api.paystack.co/{endpoint.lstrip('/')}"
    data = None
    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Origin": get_site_base_url() or "https://revledfoundation.org",
        "Referer": get_site_base_url() or "https://revledfoundation.org",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request_obj = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request_obj, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        if exc.code == 403 and "browser_signature_banned" in body:
            raise RuntimeError(
                "Paystack blocked this server request. The API is rejecting the current client fingerprint, so the donation transaction cannot be initialized until Paystack allows it."
            ) from exc
        raise RuntimeError(f"Paystack request failed: {body or exc.reason}") from exc


def initialize_paystack_transaction(email, amount_naira, reference, callback_url, metadata):
    payload = {
        "email": email,
        "amount": int(amount_naira) * 100,
        "reference": reference,
        "callback_url": callback_url,
        "metadata": metadata,
    }
    return paystack_request("POST", "transaction/initialize", payload)


def verify_paystack_transaction(reference):
    return paystack_request("GET", f"transaction/verify/{reference}")


def ensure_paystack_plan(plan_key, plan_name, amount_naira):
    setting_key = f"paystack_plan_code_{plan_key}"
    stored_code = get_app_setting(setting_key)
    if stored_code:
        return stored_code
    if not PAYSTACK_SECRET_KEY:
        return ""
    payload = {
        "name": plan_name,
        "amount": int(amount_naira) * 100,
        "interval": "monthly",
        "currency": "NGN",
    }
    response = paystack_request("POST", "plan", payload)
    plan_code = response.get("data", {}).get("plan_code", "")
    if plan_code:
        set_app_setting(setting_key, plan_code)
    return plan_code


def create_paystack_subscription(customer, plan_code, authorization_code, start_date=None):
    payload = {
        "customer": customer,
        "plan": plan_code,
        "authorization": authorization_code,
    }
    if start_date:
        payload["start_date"] = start_date
    return paystack_request("POST", "subscription", payload)


def make_reference(prefix):
    return f"{prefix}_{uuid4().hex[:20]}"


def parse_amount(value):
    cleaned = re.sub(r"[^0-9]", "", str(value or ""))
    return int(cleaned) if cleaned else 0


def coerce_int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def get_app_setting(setting_key, default=""):
    record = fetch_one("SELECT setting_value FROM payment_settings WHERE setting_key = ?", (setting_key,))
    return record["setting_value"] if record else default


def set_app_setting(setting_key, setting_value):
    now = timestamp()
    execute(
        """
        INSERT INTO payment_settings (setting_key, setting_value, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(setting_key) DO UPDATE SET
            setting_value = excluded.setting_value,
            updated_at = excluded.updated_at
        """,
        (setting_key, setting_value, now, now),
    )


def resolve_runtime_value(setting_key, default=""):
    env_value = os.environ.get(setting_key, "").strip()
    if env_value:
        return env_value
    try:
        stored_value = get_app_setting(setting_key, "").strip()
        return stored_value or default
    except RuntimeError:
        return default


def refresh_runtime_config():
    global PAYSTACK_SECRET_KEY, PAYSTACK_PUBLIC_KEY, REVLED_SITE_URL
    PAYSTACK_SECRET_KEY = get_paystack_secret_key()
    PAYSTACK_PUBLIC_KEY = get_paystack_public_key()
    REVLED_SITE_URL = get_site_base_url()


def seed_runtime_config():
    for key in [
        "SECRET_KEY",
        "REVLED_ADMIN_EMAIL",
        "REVLED_ADMIN_PASSWORD",
        "REVLED_EMAIL_USERNAME",
        "REVLED_EMAIL_PASSWORD",
        "REVLED_EMAIL_INCOMING_SERVER",
        "REVLED_EMAIL_SMTP_SERVER",
        "REVLED_EMAIL_SMTP_PORT",
        "REVLED_EMAIL_USE_SSL",
        "REVLED_EMAIL_TIMEOUT",
        "REVLED_SITE_URL",
        "PAYSTACK_SECRET_KEY",
        "PAYSTACK_PUBLIC_KEY",
    ]:
        env_value = os.environ.get(key, "").strip()
        if env_value:
            set_app_setting(key, env_value)


def get_event_capacity(event):
    seat_limit = coerce_int(event["seat_limit"], 0)
    seats_reserved = coerce_int(event["seats_reserved"], 0) if "seats_reserved" in event.keys() else 0
    seats_remaining = max(seat_limit - seats_reserved, 0) if seat_limit > 0 else None
    return {
        "seat_limit": seat_limit,
        "seats_reserved": seats_reserved,
        "seats_remaining": seats_remaining,
        "is_full": seat_limit > 0 and seats_reserved >= seat_limit,
    }


def get_program(program_slug):
    program = PROGRAMS.get(program_slug)
    if not program:
        abort(404)
    return program


def get_hub_content_config(content_type):
    config = HUB_CONTENT_TYPES.get(content_type)
    if config is None:
        abort(404)
    return config


def get_user_type_label(user_type):
    return HUB_USER_TYPES.get((user_type or "").strip().upper(), HUB_USER_TYPES["ENTREPRENEUR"])


def normalize_user_type(value):
    key = (value or "").strip().upper()
    return key if key in HUB_USER_TYPES else "ENTREPRENEUR"


def normalize_target_user_types(values):
    if not values or "ALL" in [str(value).strip().upper() for value in values]:
        return ["ALL"]
    cleaned = []
    for value in values:
        normalized = normalize_user_type(value)
        if normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned or ["ALL"]


def serialize_target_user_types(values):
    if not values or "ALL" in values:
        return "ALL"
    return ",".join(values)


def parse_target_user_types(value):
    raw = (value or "ALL").strip()
    if not raw or raw.upper() == "ALL":
        return ["ALL"]
    parsed = []
    for item in raw.split(","):
        normalized = normalize_user_type(item)
        if normalized not in parsed:
            parsed.append(normalized)
    return parsed or ["ALL"]


def format_target_user_types(value):
    items = parse_target_user_types(value)
    if "ALL" in items:
        return "All user types"
    return ", ".join(get_user_type_label(item) for item in items)


def get_member_initials(full_name):
    parts = [part for part in (full_name or "").split() if part]
    if not parts:
        return "RH"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def format_hub_member(member):
    if member is None:
        return None
    data = dict(member)
    data["initials"] = get_member_initials(data.get("full_name", ""))
    membership_labels = {
        "FULL_ACCESS": "Full Access",
        "TRIAL_EXPIRED": "Access Expired",
        "ESSENTIAL": "Free Access",
    }
    data["membership_label"] = membership_labels.get(data.get("membership_tier"), "Free Access")
    data["user_type"] = normalize_user_type(data.get("user_type") or data.get("industry_track"))
    data["user_type_label"] = get_user_type_label(data["user_type"])
    subscription = fetch_one(
        """
        SELECT status, plan_name, trial_end_at
        FROM membership_subscriptions
        WHERE email = ?
        ORDER BY
            CASE status WHEN 'active' THEN 0 WHEN 'trial' THEN 1 WHEN 'pending' THEN 2 ELSE 3 END,
            created_at DESC
        LIMIT 1
        """,
        (data.get("email", ""),),
    )
    data["subscription_status"] = subscription["status"] if subscription else ""
    data["trial_end_at"] = subscription["trial_end_at"] if subscription else ""
    data["trial_end_label"] = ""
    data["trial_days_remaining"] = None
    if subscription and subscription["trial_end_at"]:
        try:
            trial_end = datetime.strptime(subscription["trial_end_at"], "%Y-%m-%d %H:%M:%S")
            data["trial_end_label"] = trial_end.strftime("%d %B %Y")
            data["trial_days_remaining"] = max(0, (trial_end.date() - datetime.utcnow().date()).days)
        except ValueError:
            pass
    data["manual_progress_percentage"] = max(0, min(100, coerce_int(data.get("progress_percentage"), 0)))
    journey_state = build_vanguard_journey_state(data)
    data.update(journey_state)
    data["progress_percentage"] = data["journey_progress_percentage"]
    return data


def hub_detail_types():
    return {"community", "opportunities", "challenges"}


def parse_hub_start_datetime(value):
    candidate = (value or "").strip()
    if not candidate:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


def is_hub_content_released(entry):
    start_dt = parse_hub_start_datetime(entry.get("starts_at") if isinstance(entry, dict) else getattr(entry, "starts_at", None))
    if start_dt is None:
        return True
    return start_dt <= datetime.utcnow()


def hub_member_can_see(member, entry):
    if member is None:
        return False
    if int(entry.get("is_published", 1) or 0) != 1:
        return False
    membership_tier = (member["membership_tier"] if "membership_tier" in member.keys() else member.get("membership_tier")) or "ESSENTIAL"
    if membership_tier == "TRIAL_EXPIRED":
        return False

    access_tier = (entry["access_tier"] if "access_tier" in entry.keys() else "ALL") or "ALL"
    if access_tier == "ALL":
        tier_allowed = True
    else:
        tier_allowed = membership_tier == "FULL_ACCESS" or membership_tier == access_tier

    if not tier_allowed or member is None:
        return tier_allowed and member is not None

    member_user_type = normalize_user_type(member["user_type"] if "user_type" in member.keys() else member.get("user_type"))
    target_user_types = parse_target_user_types(entry["audience_user_types"] if "audience_user_types" in entry.keys() else entry.get("audience_user_types"))
    return "ALL" in target_user_types or member_user_type in target_user_types


def hub_member_can_access(member, entry):
    if not hub_member_can_see(member, entry):
        return False
    return is_hub_content_released(entry)


def format_hub_entry(entry):
    data = dict(entry)
    data["target_user_types"] = parse_target_user_types(data.get("audience_user_types"))
    data["target_user_types_label"] = format_target_user_types(data.get("audience_user_types"))
    data["has_uploaded_file"] = bool(data.get("uploaded_file"))
    data["is_released"] = is_hub_content_released(data)
    data["release_label"] = ""
    if data.get("starts_at"):
        try:
            dt = datetime.strptime(data["starts_at"], "%Y-%m-%d %H:%M:%S")
            data["release_label"] = dt.strftime("%d %b %Y")
        except ValueError:
            try:
                data["release_label"] = datetime.fromisoformat(data["starts_at"].replace("Z", "+00:00")).strftime("%d %b %Y")
            except ValueError:
                data["release_label"] = ""
    if data["content_type"] == "resources" and data.get("uploaded_file"):
        data["resource_link"] = url_for("hub_resource_view", item_id=data["id"])
    elif data["content_type"] in hub_detail_types():
        data["resource_link"] = url_for("hub_content_detail", content_type=data["content_type"], item_id=data["id"])
    else:
        data["resource_link"] = data.get("cta_url") or ""
    return data


def fetch_hub_content_item(item_id):
    item = fetch_one("SELECT * FROM hub_content WHERE id = ?", (item_id,))
    return format_hub_entry(item) if item else None


def get_hub_content_item_for_member(item_id, member, content_type=None, published_only=True):
    query = "SELECT * FROM hub_content WHERE id = ?"
    params = [item_id]
    if content_type:
        query += " AND content_type = ?"
        params.append(content_type)
    if published_only:
        query += " AND is_published = 1"
    item = fetch_one(query, tuple(params))
    if item is None:
        abort(404)
    formatted = format_hub_entry(item)
    if not hub_member_can_access(member, formatted):
        abort(403)
    return formatted


def is_member_joined_to_content(content_id, member_id):
    return fetch_one(
        "SELECT id FROM hub_content_memberships WHERE content_id = ? AND member_id = ?",
        (content_id, member_id),
    ) is not None


def count_hub_memberships(content_id):
    return fetch_one(
        "SELECT COUNT(*) AS total FROM hub_content_memberships WHERE content_id = ?",
        (content_id,),
    )["total"]


def fetch_hub_messages(content_id):
    return fetch_all(
        """
        SELECT hm.*, m.full_name, m.user_type
        FROM hub_messages hm
        JOIN hub_members m ON m.id = hm.member_id
        WHERE hm.content_id = ?
        ORDER BY hm.created_at ASC
        """,
        (content_id,),
    )


def create_password_reset(member):
    token = secrets.token_urlsafe(32)
    expiry_string = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    execute(
        "UPDATE password_reset_tokens SET used_at = ? WHERE member_id = ? AND used_at IS NULL",
        (timestamp(), member["id"]),
    )
    execute(
        "INSERT INTO password_reset_tokens (member_id, token, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (member["id"], token, expiry_string, timestamp()),
    )
    return token, expiry_string


def get_active_password_reset(token):
    record = fetch_one(
        """
        SELECT prt.*, hm.full_name, hm.email
        FROM password_reset_tokens prt
        JOIN hub_members hm ON hm.id = prt.member_id
        WHERE prt.token = ? AND prt.used_at IS NULL
        """,
        (token,),
    )
    if record is None:
        return None
    if (record["expires_at"] or "") < timestamp():
        return None
    return record


def format_blog_content_html(content):
    content = (content or "").strip()
    if not content:
        return ""
    if re.search(r"</?[a-z][\s\S]*>", content, re.IGNORECASE):
        return content
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    return "".join(f"<p>{paragraph.replace(chr(10), '<br>')}</p>" for paragraph in paragraphs)


def fetch_hub_content(content_type, member=None, published_only=True, limit=None):
    get_hub_content_config(content_type)
    query = "SELECT * FROM hub_content WHERE content_type = ?"
    params = [content_type]
    if published_only:
        query += " AND is_published = 1"
    query += " ORDER BY sort_order ASC, COALESCE(starts_at, created_at) ASC, created_at DESC"
    if limit:
        query += f" LIMIT {int(limit)}"
    entries = [format_hub_entry(entry) for entry in fetch_all(query, tuple(params))]
    if member is not None:
        return [entry for entry in entries if hub_member_can_see(member, entry)]
    return entries


def count_hub_content(content_type, member=None):
    entries = fetch_hub_content(content_type, member=member, published_only=True)
    return len(entries)


VANGUARD_JOURNEY_SETTING_KEY = "vanguard_journey_config"
DEFAULT_VANGUARD_JOURNEY_CONFIG = {
    "activities": [
        "career-starter-cv-template",
        "industry-positioning-lab",
        "build-your-linkedin-profile",
        "entertainment-peer-room",
        "junior-content-strategist-internship",
    ],
    "stages": [
        {
            "label": "First Spark",
            "min_completed": 1,
            "copy": "You’ve completed your first real activity. Keep going to turn that spark into momentum.",
            "next_label": "Keep the spark going",
        },
        {
            "label": "Momentum Maker",
            "min_completed": 3,
            "copy": "You’re stacking real progress across the hub. Finish the remaining key activities and you’ll be certificate ready.",
            "next_label": "Final stretch ahead",
        },
        {
            "label": "Certificate Ready",
            "min_completed": 5,
            "copy": "You’ve completed every tracked Vanguard activity. You’re ready for the completion certificate.",
            "next_label": "Completion achieved",
        },
    ],
}


def normalize_vanguard_journey_config(raw_config):
    config = dict(DEFAULT_VANGUARD_JOURNEY_CONFIG)
    if isinstance(raw_config, dict):
        activities = raw_config.get("activities")
        if isinstance(activities, list) and activities:
            config["activities"] = [slugify(item) for item in activities if slugify(item)]
        stages = raw_config.get("stages")
        if isinstance(stages, list) and stages:
            normalized_stages = []
            for stage in stages:
                if not isinstance(stage, dict):
                    continue
                label = (stage.get("label") or "").strip()
                copy = (stage.get("copy") or "").strip()
                next_label = (stage.get("next_label") or "").strip()
                min_completed = coerce_int(stage.get("min_completed"), 0)
                if label and copy and next_label and min_completed > 0:
                    normalized_stages.append(
                        {
                            "label": label,
                            "min_completed": min_completed,
                            "copy": copy,
                            "next_label": next_label,
                        }
                    )
            if normalized_stages:
                normalized_stages.sort(key=lambda item: item["min_completed"])
                config["stages"] = normalized_stages
    return config


def get_vanguard_journey_config():
    raw_value = get_app_setting(VANGUARD_JOURNEY_SETTING_KEY, "")
    if not raw_value:
        return dict(DEFAULT_VANGUARD_JOURNEY_CONFIG)
    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return dict(DEFAULT_VANGUARD_JOURNEY_CONFIG)
    return normalize_vanguard_journey_config(parsed)


def save_vanguard_journey_config(config):
    set_app_setting(VANGUARD_JOURNEY_SETTING_KEY, json.dumps(normalize_vanguard_journey_config(config), ensure_ascii=False))


def get_vanguard_completion_rows(member_id):
    return fetch_all(
        """
        SELECT hc.id, hc.slug, hc.title, hc.content_type, hcm.joined_at
        FROM hub_content_memberships hcm
        JOIN hub_content hc ON hc.id = hcm.content_id
        WHERE hcm.member_id = ?
        ORDER BY hcm.joined_at ASC, hc.sort_order ASC, hc.id ASC
        """,
        (member_id,),
    )


def build_vanguard_journey_state(member):
    journey_config = get_vanguard_journey_config()
    tracked_slugs = journey_config["activities"]
    journey_stages = journey_config["stages"]
    if member is None:
        return {
            "journey_completed_count": 0,
            "journey_total_count": len(tracked_slugs),
            "journey_completed_slugs": [],
            "journey_completed_titles": [],
            "journey_badge_label": "Getting Started",
            "journey_badge_copy": "Join your first guided activity to unlock your first badge.",
            "journey_next_label": "First activity ahead",
            "journey_progress_percentage": 0,
        }

    completion_rows = get_vanguard_completion_rows(member["id"])
    completed_slug_order = []
    completed_titles = []
    completed_slug_set = set()
    for row in completion_rows:
        slug = row["slug"]
        if slug in tracked_slugs and slug not in completed_slug_set:
            completed_slug_set.add(slug)
            completed_slug_order.append(slug)
            completed_titles.append(row["title"])

    completed_count = len(completed_slug_order)
    total_count = len(tracked_slugs)
    progress_percentage = int(round((completed_count / total_count) * 100)) if total_count else 0

    badge_label = "Getting Started"
    badge_copy = "Join your first guided activity to unlock your first badge."
    next_label = "First activity ahead"

    for stage in journey_stages:
        if completed_count >= stage["min_completed"]:
            badge_label = stage["label"]
            badge_copy = stage["copy"]
            next_label = stage["next_label"]

    if completed_count >= total_count:
        next_label = "Completion achieved"

    next_required_title = ""
    for slug in tracked_slugs:
        if slug not in completed_slug_set:
            next_required = fetch_one(
                "SELECT title FROM hub_content WHERE slug = ?",
                (slug,),
            )
            next_required_title = next_required["title"] if next_required else ""
            break

    if completed_count == 0 and next_required_title:
        badge_copy = f"Complete {next_required_title} to unlock your first milestone."
    elif completed_count < total_count and next_required_title:
        badge_copy = f"{badge_copy} Next up: {next_required_title}."

    return {
        "journey_completed_count": completed_count,
        "journey_total_count": total_count,
        "journey_completed_slugs": completed_slug_order,
        "journey_completed_titles": completed_titles,
        "journey_badge_label": badge_label,
        "journey_badge_copy": badge_copy,
        "journey_next_label": next_label,
        "journey_progress_percentage": progress_percentage,
    }


def build_hub_stats(member):
    return {
        "schedule": count_hub_content("schedule", member=member),
        "resources": count_hub_content("resources", member=member),
        "community": count_hub_content("community", member=member),
        "opportunities": count_hub_content("opportunities", member=member),
        "challenges": count_hub_content("challenges", member=member),
    }


MEMBERSHIP_PLANS = {
    "trial": {
        "plan_code": "FREE_VANGUARD_ACCESS",
        "name": "FREE VANGUARD ACCESS",
        "amount_naira": 0,
        "best_for": "Students and young people exploring career options",
    },
    "plus": {
        "plan_code": "VANGUARD_PLUS",
        "name": "VANGUARD PLUS",
        "amount_naira": 5000,
        "best_for": "Young professionals seeking career growth and opportunities",
    },
    "pro": {
        "plan_code": "VANGUARD_PRO",
        "name": "VANGUARD PRO",
        "amount_naira": 10000,
        "best_for": "Ambitious young professionals seeking accelerated career growth",
    },
}


def get_membership_plan(plan_key):
    return MEMBERSHIP_PLANS.get((plan_key or "").strip().lower(), MEMBERSHIP_PLANS["trial"])


def donation_payload_summary(record):
    return {
        "reference": record["reference"],
        "donor_name": record["donor_name"],
        "donor_email": record["donor_email"],
        "amount_naira": record["amount_naira"],
        "status": record["status"],
        "paystack_status": record["paystack_status"],
    }


def membership_payload_summary(record):
    return {
        "reference": record["reference"],
        "full_name": record["full_name"],
        "email": record["email"],
        "plan_name": record["plan_name"],
        "amount_naira": record["amount_naira"],
        "status": record["status"],
        "trial_end_at": record["trial_end_at"],
        "next_billing_at": record["next_billing_at"],
    }


def seed_initial_content(db):
    event = db.execute("SELECT id FROM events LIMIT 1").fetchone()
    if event is None:
        now = timestamp()
        db.execute(
            """
            INSERT INTO events (
                title, slug, summary, description, location, event_type, program_slug, start_date, end_date,
                booking_link, registration_label, requires_registration, is_published, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Holiday Skills Bootcamp",
                "holiday-skills-bootcamp",
                "A school-break bootcamp blending creativity, teamwork, and practical skills.",
                "This holiday bootcamp gives children and teenagers a structured, energising environment to build confidence, explore skills, and complete a guided project with Revled facilitators.",
                "Lagos, Nigeria",
                "bootcamp",
                "explorers",
                "2026-08-10",
                "2026-08-21",
                "",
                "Reserve a Place",
                1,
                1,
                now,
                now,
            ),
        )

    resource = db.execute("SELECT id FROM resources LIMIT 1").fetchone()
    if resource is None:
        now = timestamp()
        db.execute(
            """
            INSERT INTO resources (
                title, slug, resource_type, audience, summary, description, price_naira, external_url,
                cta_label, uploaded_file, is_published, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Revled Parent Activity Pack",
                "revled-parent-activity-pack",
                "guide",
                "parents",
                "A practical starter pack with simple activities for home-based learning and reflection.",
                "Use these printable prompts and conversation starters to reinforce confidence, curiosity, and emotional awareness at home.",
                0,
                "",
                "Access Guide",
                "",
                1,
                now,
                now,
            ),
        )


def seed_hub_content(db):
    item = db.execute("SELECT id FROM hub_content LIMIT 1").fetchone()
    if item is not None:
        return

    now = timestamp()
    sample_entries = [
        (
            "schedule",
            "industry-positioning-lab",
            "Industry Positioning Lab",
            "A live class on packaging your strengths for the roles you actually want.",
            "Join the weekly positioning lab with practical examples and direct guidance for members building career clarity.",
            "Tosin Ojo",
            "Live class",
            "2026-04-28 17:00:00",
            "",
            "Virtual",
            "Live next",
            "Featured",
            "Join live",
            "",
            "ALL",
            1,
            1,
            now,
            now,
        ),
        (
            "resources",
            "career-starter-cv-template",
            "Career Starter CV Template",
            "A clean, recruiter-friendly CV template for students and early-career members.",
            "Use this editable template to structure your story, projects, and work experience with more confidence.",
            "Template",
            "All members",
            "",
            "",
            "",
            "Fresh drop",
            "PDF",
            "Open template",
            "",
            "ALL",
            2,
            1,
            now,
            now,
        ),
        (
            "community",
            "entertainment-peer-room",
            "Entertainment Peer Room",
            "A focused space for members building in film, media, content, and entertainment.",
            "Meet peers, share drafts, and join weekly accountability check-ins inside the entertainment track.",
            "Revled Team",
            "32 active members",
            "2026-04-30 18:30:00",
            "",
            "Hub room",
            "Open room",
            "Peer circle",
            "Enter room",
            "",
            "ALL",
            3,
            1,
            now,
            now,
        ),
        (
            "opportunities",
            "junior-content-strategist-internship",
            "Junior Content Strategist Internship",
            "A remote internship opening for members with strong writing and audience instincts.",
            "Build campaign support materials, research content ideas, and learn inside a fast-moving creative team.",
            "Studio North",
            "Internship",
            "2026-05-05 23:59:00",
            "",
            "Remote",
            "Closing soon",
            "Paid",
            "Apply now",
            "",
            "FULL_ACCESS",
            4,
            1,
            now,
            now,
        ),
        (
            "challenges",
            "build-your-linkedin-profile",
            "Build Your LinkedIn Profile",
            "Complete your headline, about section, and featured work before the next review clinic.",
            "This challenge helps members create a sharper first impression before applying for opportunities.",
            "Beginner",
            "Personal brand upgrade",
            "",
            "",
            "",
            "In progress",
            "Weekly challenge",
            "View checklist",
            "",
            "ALL",
            5,
            1,
            now,
            now,
        ),
    ]
    db.executemany(
        """
        INSERT INTO hub_content (
            content_type, slug, title, summary, description, meta_one, meta_two, starts_at, ends_at, location,
            status_text, badge_text, cta_label, cta_url, audience_user_types, uploaded_file, uploaded_file_name,
            access_tier, sort_order, is_published, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        sample_entries,
    )


def init_db():
    ensure_directory(RESOURCE_UPLOAD_DIR)
    ensure_directory(BLOG_UPLOAD_DIR)
    ensure_directory(HUB_UPLOAD_DIR)
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS program_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_slug TEXT NOT NULL,
            program_name TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            applicant_age TEXT NOT NULL,
            city TEXT NOT NULL,
            state_region TEXT NOT NULL,
            guardian_name TEXT,
            guardian_phone TEXT,
            school_or_work TEXT,
            goals TEXT NOT NULL,
            interest_reason TEXT NOT NULL,
            preferred_start TEXT,
            follow_up_status TEXT NOT NULL DEFAULT 'new',
            follow_up_notes TEXT,
            admin_notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS blog_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            excerpt TEXT NOT NULL,
            content TEXT NOT NULL,
            image_url TEXT,
            is_published INTEGER NOT NULL DEFAULT 1,
            published_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS blog_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            content TEXT NOT NULL,
            is_approved INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY(post_id) REFERENCES blog_posts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS blog_likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            visitor_token TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(post_id, visitor_token),
            FOREIGN KEY(post_id) REFERENCES blog_posts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            summary TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            event_type TEXT NOT NULL,
            program_slug TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT,
            booking_link TEXT,
            registration_label TEXT,
            seat_limit INTEGER NOT NULL DEFAULT 0,
            requires_registration INTEGER NOT NULL DEFAULT 0,
            is_published INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS event_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            organization TEXT,
            notes TEXT,
            seat_count INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            resource_type TEXT NOT NULL,
            audience TEXT NOT NULL,
            summary TEXT NOT NULL,
            description TEXT NOT NULL,
            price_naira INTEGER NOT NULL DEFAULT 0,
            external_url TEXT,
            cta_label TEXT,
            uploaded_file TEXT,
            is_published INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS consultation_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            organization TEXT,
            consultation_type TEXT NOT NULL,
            preferred_date TEXT,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            admin_notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            admin_notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS donation_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT NOT NULL UNIQUE,
            donor_name TEXT NOT NULL,
            donor_email TEXT NOT NULL,
            amount_naira INTEGER NOT NULL DEFAULT 0,
            message TEXT,
            payment_type TEXT NOT NULL DEFAULT 'donation',
            source TEXT NOT NULL DEFAULT 'website',
            status TEXT NOT NULL DEFAULT 'pending',
            paystack_status TEXT,
            paystack_response TEXT,
            verified_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS membership_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            plan_code TEXT NOT NULL,
            plan_name TEXT NOT NULL,
            amount_naira INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'trial',
            trial_start_at TEXT,
            trial_end_at TEXT,
            trial_reminder_sent_at TEXT,
            next_billing_at TEXT,
            cancellation_at TEXT,
            paystack_plan_code TEXT,
            paystack_customer_code TEXT,
            paystack_subscription_code TEXT,
            paystack_authorization_code TEXT,
            paystack_response TEXT,
            source TEXT NOT NULL DEFAULT 'website',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS payment_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS enquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enquiry_type TEXT NOT NULL,
            program_slug TEXT,
            program_name TEXT,
            contact_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            organization TEXT,
            child_name TEXT,
            child_age TEXT,
            location TEXT,
            preferred_term TEXT,
            budget_range TEXT,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            admin_notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS hub_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            user_type TEXT NOT NULL DEFAULT 'ENTREPRENEUR',
            industry_track TEXT NOT NULL DEFAULT 'General',
            membership_tier TEXT NOT NULL DEFAULT 'ESSENTIAL',
            progress_percentage INTEGER NOT NULL DEFAULT 0,
            bio TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS hub_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            description TEXT NOT NULL,
            meta_one TEXT,
            meta_two TEXT,
            starts_at TEXT,
            ends_at TEXT,
            location TEXT,
            status_text TEXT,
            badge_text TEXT,
            cta_label TEXT,
            cta_url TEXT,
            audience_user_types TEXT NOT NULL DEFAULT 'ALL',
            uploaded_file TEXT,
            uploaded_file_name TEXT,
            access_tier TEXT NOT NULL DEFAULT 'ALL',
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_published INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS hub_content_memberships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            joined_at TEXT NOT NULL,
            UNIQUE(content_id, member_id),
            FOREIGN KEY(content_id) REFERENCES hub_content(id) ON DELETE CASCADE,
            FOREIGN KEY(member_id) REFERENCES hub_members(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS hub_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(content_id) REFERENCES hub_content(id) ON DELETE CASCADE,
            FOREIGN KEY(member_id) REFERENCES hub_members(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS community_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            is_hidden INTEGER NOT NULL DEFAULT 0,
            is_pinned INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES hub_members(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS community_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            parent_reply_id INTEGER,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            is_hidden INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(post_id) REFERENCES community_posts(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES hub_members(id) ON DELETE CASCADE,
            FOREIGN KEY(parent_reply_id) REFERENCES community_replies(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS community_user_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_type TEXT NOT NULL,
            awarded_by INTEGER NOT NULL,
            awarded_at TEXT NOT NULL,
            revoked_at TEXT,
            FOREIGN KEY(user_id) REFERENCES hub_members(id) ON DELETE CASCADE,
            FOREIGN KEY(awarded_by) REFERENCES admins(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS community_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER NOT NULL,
            post_id INTEGER,
            reply_id INTEGER,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            resolved_by INTEGER,
            FOREIGN KEY(reporter_id) REFERENCES hub_members(id) ON DELETE CASCADE,
            FOREIGN KEY(post_id) REFERENCES community_posts(id) ON DELETE CASCADE,
            FOREIGN KEY(reply_id) REFERENCES community_replies(id) ON DELETE CASCADE,
            FOREIGN KEY(resolved_by) REFERENCES admins(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_community_posts_feed
            ON community_posts(is_deleted, is_hidden, is_pinned, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_community_replies_post
            ON community_replies(post_id, is_deleted, is_hidden, created_at ASC);
        CREATE INDEX IF NOT EXISTS idx_community_badges_active
            ON community_user_badges(user_id, badge_type, revoked_at);
        CREATE INDEX IF NOT EXISTS idx_community_reports_status
            ON community_reports(status, created_at DESC);

        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(member_id) REFERENCES hub_members(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS admin_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            source_table TEXT,
            source_id INTEGER,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS vanguard_mentor_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            current_role_org TEXT NOT NULL,
            industry TEXT NOT NULL,
            other_industry TEXT NOT NULL DEFAULT '',
            availability TEXT NOT NULL DEFAULT '',
            frequency TEXT NOT NULL DEFAULT '',
            availability_notes TEXT NOT NULL DEFAULT '',
            topics TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'new',
            admin_notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS catalyst_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            current_role_org TEXT NOT NULL DEFAULT '',
            involvement_type TEXT NOT NULL,
            skill_area TEXT NOT NULL,
            other_skill TEXT NOT NULL DEFAULT '',
            availability TEXT NOT NULL DEFAULT '',
            availability_notes TEXT NOT NULL DEFAULT '',
            additional_notes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'new',
            admin_notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    ensure_column(db, "blog_posts", "image_url", "TEXT")
    ensure_column(db, "events", "seat_limit", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(db, "event_registrations", "seat_count", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(db, "hub_members", "user_type", "TEXT NOT NULL DEFAULT 'ENTREPRENEUR'")
    ensure_column(db, "hub_content", "audience_user_types", "TEXT NOT NULL DEFAULT 'ALL'")
    ensure_column(db, "hub_content", "uploaded_file", "TEXT")
    ensure_column(db, "hub_content", "uploaded_file_name", "TEXT")
    ensure_column(db, "donation_payments", "payment_type", "TEXT NOT NULL DEFAULT 'donation'")
    ensure_column(db, "donation_payments", "source", "TEXT NOT NULL DEFAULT 'website'")
    ensure_column(db, "donation_payments", "status", "TEXT NOT NULL DEFAULT 'pending'")
    ensure_column(db, "donation_payments", "paystack_status", "TEXT")
    ensure_column(db, "donation_payments", "paystack_response", "TEXT")
    ensure_column(db, "donation_payments", "verified_at", "TEXT")
    ensure_column(db, "membership_subscriptions", "plan_code", "TEXT NOT NULL DEFAULT ''")
    ensure_column(db, "membership_subscriptions", "plan_name", "TEXT NOT NULL DEFAULT ''")
    ensure_column(db, "membership_subscriptions", "amount_naira", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(db, "membership_subscriptions", "status", "TEXT NOT NULL DEFAULT 'trial'")
    ensure_column(db, "membership_subscriptions", "trial_start_at", "TEXT")
    ensure_column(db, "membership_subscriptions", "trial_end_at", "TEXT")
    ensure_column(db, "membership_subscriptions", "trial_reminder_sent_at", "TEXT")
    ensure_column(db, "membership_subscriptions", "next_billing_at", "TEXT")
    ensure_column(db, "membership_subscriptions", "cancellation_at", "TEXT")
    ensure_column(db, "membership_subscriptions", "paystack_plan_code", "TEXT")
    ensure_column(db, "membership_subscriptions", "paystack_customer_code", "TEXT")
    ensure_column(db, "membership_subscriptions", "paystack_subscription_code", "TEXT")
    ensure_column(db, "membership_subscriptions", "paystack_authorization_code", "TEXT")
    ensure_column(db, "membership_subscriptions", "paystack_response", "TEXT")

    # Migrate any existing subscriptions using the old plan code to the new plan code
    try:
        db.execute(
            """
            UPDATE membership_subscriptions
            SET plan_code = ?, plan_name = ?
            WHERE plan_code = ?
            """,
            (
                "FREE_TRIAL_1_MONTH",
                "FREE 1-Month Trial",
                "FREE_TRIAL_2_MONTHS",
            ),
        )
    except Exception:
        # Ignore migration errors here; they can be investigated by ops if needed
        pass

    untracked_members = db.execute(
        """
        SELECT hm.full_name, hm.email
        FROM hub_members hm
        WHERE hm.membership_tier != 'FULL_ACCESS'
          AND NOT EXISTS (
              SELECT 1 FROM membership_subscriptions ms WHERE ms.email = hm.email
          )
        """
    ).fetchall()
    if untracked_members:
        migration_start = timestamp()
        migration_end = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        for member in untracked_members:
            db.execute(
                """
                INSERT INTO membership_subscriptions (
                    reference, full_name, email, plan_code, plan_name, amount_naira, status,
                    trial_start_at, trial_end_at, next_billing_at, cancellation_at,
                    paystack_plan_code, paystack_customer_code, paystack_subscription_code,
                    paystack_authorization_code, paystack_response, source, created_at, updated_at
                )
                VALUES (?, ?, ?, 'FREE_TRIAL_1_MONTH', 'FREE 1-Month Trial', 0, 'trial',
                        ?, ?, '', '', '', '', '', '', '', 'account_migration', ?, ?)
                """,
                (
                    make_reference("membership"),
                    member["full_name"],
                    member["email"],
                    migration_start,
                    migration_end,
                    migration_start,
                    migration_start,
                ),
            )

    admin = db.execute("SELECT id FROM admins WHERE email = ?", (DEFAULT_ADMIN_EMAIL,)).fetchone()
    if admin is None:
        db.execute(
            """
            INSERT INTO admins (full_name, email, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("Revled Admin", DEFAULT_ADMIN_EMAIL, hash_password(DEFAULT_ADMIN_PASSWORD), timestamp()),
        )

    db.execute("DELETE FROM events WHERE slug = ?", ("holiday-skills-bootcamp",))
    db.execute("DELETE FROM resources WHERE slug = ?", ("revled-parent-activity-pack",))
    db.execute(
        "DELETE FROM hub_content WHERE slug IN (?, ?, ?, ?, ?)",
        (
            "industry-positioning-lab",
            "career-starter-cv-template",
            "entertainment-peer-room",
            "junior-content-strategist-internship",
            "build-your-linkedin-profile",
        ),
    )

    db.commit()
    db.close()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Please log in to access the admin dashboard.", "error")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped_view


def hub_login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("hub_member_id"):
            flash("Sign in to access the hub.", "error")
            return redirect(url_for("hub_login"))
        return view(*args, **kwargs)

    return wrapped_view


def community_member_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not g.get("current_hub_member"):
            return jsonify({"error": "Authentication required."}), 401
        return view(*args, **kwargs)

    return wrapped_view


def community_is_moderator(member_id):
    if g.get("current_admin") is not None:
        return True
    return fetch_one(
        """
        SELECT id FROM community_user_badges
        WHERE user_id = ? AND badge_type = 'moderator' AND revoked_at IS NULL
        LIMIT 1
        """,
        (member_id,),
    ) is not None


def community_content_authorized(row, member_id):
    return row and (row["user_id"] == member_id or community_is_moderator(member_id))


def community_member_payload(member_id):
    member = fetch_one(
        """
        SELECT hm.id, hm.full_name, hm.email,
               EXISTS(SELECT 1 FROM admins a WHERE lower(a.email) = lower(hm.email)) AS is_admin
        FROM hub_members hm WHERE hm.id = ?
        """,
        (member_id,),
    )
    if member is None:
        return None
    return {
        "id": member["id"],
        "name": member["full_name"],
        "initials": get_member_initials(member["full_name"]),
        "is_moderator": bool(member["is_admin"]) or community_is_moderator(member_id),
    }


def community_author_payload(user_id):
    member = community_member_payload(user_id)
    if member is None:
        return {"id": user_id, "name": "Member", "initials": "M", "is_moderator": False}
    return member


def community_relative_time(value):
    try:
        created = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return value or ""
    seconds = max(0, int((datetime.utcnow() - created).total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    if seconds < 604800:
        return f"{seconds // 86400}d ago"
    return created.strftime("%d %b %Y")


def community_reply_payload(row):
    payload = dict(row)
    payload["author"] = community_author_payload(row["user_id"])
    payload["relative_time"] = community_relative_time(row["created_at"])
    return payload


def community_post_payload(row, include_replies=False):
    payload = dict(row)
    payload["author"] = community_author_payload(row["user_id"])
    payload["relative_time"] = community_relative_time(row["created_at"])
    payload["reply_count"] = fetch_one(
        "SELECT COUNT(*) AS total FROM community_replies WHERE post_id = ? AND is_deleted = 0 AND is_hidden = 0",
        (row["id"],),
    )["total"]
    if include_replies:
        payload["replies"] = [
            community_reply_payload(reply)
            for reply in fetch_all(
                """
                SELECT * FROM community_replies
                WHERE post_id = ? AND is_deleted = 0 AND is_hidden = 0
                ORDER BY created_at ASC, id ASC
                """,
                (row["id"],),
            )
        ]
    return payload


def resolve_program_action(program, action_type, enquiry_type=None, anchor=""):
    if action_type == "register":
        return url_for("program_register", program_slug=program["slug"])
    if action_type == "resources":
        target = url_for("resources")
        return f"{target}#{anchor}" if anchor else target
    if action_type == "youtube":
        return "https://www.youtube.com/channel/UCq5_9_lchriuRnKLCFviLUg"
    if action_type == "consultation":
        target = url_for("book_consultation")
        return f"{target}#{anchor}" if anchor else target
    if action_type == "events":
        target = url_for("events_list")
        return f"{target}#{anchor}" if anchor else target
    if action_type == "vanguard":
        return url_for("vanguard_hub_signup")
    if action_type == "contact":
        target = url_for("contact")
        return f"{target}#{anchor}" if anchor else target
    if action_type == "anchor":
        return f"#{anchor}" if anchor else "#"
    if action_type == "enquiry" and enquiry_type:
        return url_for("programme_enquiry", program_slug=program["slug"], enquiry_type=enquiry_type)
    return "#"


def format_program_for_template(program):
    data = dict(program)
    data["primary_cta_url"] = resolve_program_action(
        program,
        program.get("primary_cta_type", "register"),
        enquiry_type=program.get("primary_enquiry_type"),
        anchor=program.get("primary_cta_anchor", ""),
    )
    data["secondary_cta_url"] = resolve_program_action(
        program,
        program.get("secondary_cta_type", "enquiry"),
        enquiry_type=program.get("secondary_enquiry_type"),
        anchor=program.get("secondary_anchor", ""),
    )
    data["business_ctas_resolved"] = [
        {
            "label": item["label"],
            "url": resolve_program_action(program, item["url_type"], enquiry_type=item.get("enquiry_type"), anchor=item.get("anchor", "")),
        }
        for item in program.get("business_ctas", [])
    ]
    school_cta = program.get("school_cta")
    if school_cta:
        data["school_cta_url"] = resolve_program_action(
            program,
            school_cta["url_type"],
            enquiry_type=school_cta.get("enquiry_type"),
            anchor=school_cta.get("anchor", ""),
        )
    else:
        data["school_cta_url"] = "#"
    return data


def record_donation_payment(form_data):
    amount_naira = parse_amount(form_data.get("amount"))
    if amount_naira <= 0:
        raise ValueError("Please enter a donation amount greater than zero.")
    donor_name = (form_data.get("donor_name") or "").strip()
    donor_email = (form_data.get("donor_email") or "").strip().lower()
    if not donor_name or not donor_email:
        raise ValueError("Please provide your name and email address.")
    reference = make_reference("donation")
    now = timestamp()
    execute(
        """
        INSERT INTO donation_payments (
            reference, donor_name, donor_email, amount_naira, message, payment_type, source,
            status, paystack_status, paystack_response, verified_at, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, 'donation', 'website', 'pending', '', '', '', ?, ?)
        """,
        (
            reference,
            donor_name,
            donor_email,
            amount_naira,
            (form_data.get("message") or "").strip(),
            now,
            now,
        ),
    )
    return reference


def update_donation_payment(reference, paystack_data, status="success"):
    now = timestamp()
    execute(
        """
        UPDATE donation_payments
        SET status = ?, paystack_status = ?, paystack_response = ?, verified_at = ?, updated_at = ?
        WHERE reference = ?
        """,
        (
            status,
            paystack_data.get("data", {}).get("status", ""),
            json.dumps(paystack_data),
            now,
            now,
            reference,
        ),
    )


def record_membership_subscription(form_data):
    plan = get_membership_plan(form_data.get("plan"))
    full_name = (form_data.get("full_name") or "").strip()
    email = (form_data.get("email") or "").strip().lower()
    password = (form_data.get("password") or "").strip()
    user_type = normalize_user_type(form_data.get("user_type") or "PROFESSIONAL")
    if not full_name or not email or not password:
        raise ValueError("Please complete your name, email, and password.")
    if len(password) < 8:
        raise ValueError("Use a password with at least 8 characters.")
    existing_member = fetch_one("SELECT id FROM hub_members WHERE email = ?", (email,))
    if existing_member is not None:
        raise ValueError("An account with that email already exists. Sign in to manage or upgrade your membership.")
    reference = make_reference("membership")
    now = timestamp()
    trial_start = now
    trial_end_string = (
        (datetime.utcnow() + timedelta(days=30)).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        if plan["amount_naira"] > 0 else ""
    )
    next_billing_string = trial_end_string if plan["amount_naira"] > 0 else ""
    paystack_plan_code = ""
    if plan["amount_naira"] > 0:
        paystack_plan_code = ensure_paystack_plan(plan["plan_code"], plan["name"], plan["amount_naira"])
    execute(
        """
        INSERT INTO hub_members (
            full_name, email, password_hash, user_type, industry_track, membership_tier, progress_percentage,
            bio, is_active, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 0, '', 1, ?, ?)
        """,
        (
            full_name,
            email,
            hash_password(password),
            user_type,
            plan["name"],
            "ESSENTIAL",
            now,
            now,
        ),
    )
    execute(
        """
        INSERT INTO membership_subscriptions (
            reference, full_name, email, plan_code, plan_name, amount_naira, status, trial_start_at, trial_end_at,
            next_billing_at, cancellation_at, paystack_plan_code, paystack_customer_code, paystack_subscription_code,
            paystack_authorization_code, paystack_response, source, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, '', '', '', '', 'website', ?, ?)
        """,
        (
            reference,
            full_name,
            email,
            plan["plan_code"],
            plan["name"],
            plan["amount_naira"],
            "active" if plan["amount_naira"] == 0 else "pending",
            trial_start,
            trial_end_string,
            next_billing_string,
            paystack_plan_code,
            now,
            now,
        ),
    )
    return reference, plan, trial_start, trial_end_string


def start_membership_checkout(member, plan_key):
    plan = get_membership_plan(plan_key)
    if plan["amount_naira"] <= 0:
        raise ValueError("Select a paid membership plan to continue to checkout.")
    reference = make_reference("membership")
    now = timestamp()
    trial_start = now
    trial_end_string = (datetime.utcnow() + timedelta(days=30)).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    paystack_plan_code = ensure_paystack_plan(plan["plan_code"], plan["name"], plan["amount_naira"])
    execute(
        """
        INSERT INTO membership_subscriptions (
            reference, full_name, email, plan_code, plan_name, amount_naira, status, trial_start_at, trial_end_at,
            next_billing_at, cancellation_at, paystack_plan_code, paystack_customer_code, paystack_subscription_code,
            paystack_authorization_code, paystack_response, source, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, '', '', '', '', 'website', ?, ?)
        """,
        (
            reference,
            member["full_name"],
            member["email"],
            plan["plan_code"],
            plan["name"],
            plan["amount_naira"],
            "pending",
            trial_start,
            trial_end_string,
            trial_end_string,
            paystack_plan_code,
            now,
            now,
        ),
    )
    try:
        callback_url = build_absolute_url(url_for("vanguard_hub_callback"))
        payment_data = initialize_paystack_transaction(
            member["email"],
            plan["amount_naira"],
            reference,
            callback_url,
            {
                "payment_type": "membership",
                "plan_code": plan["plan_code"],
                "plan_name": plan["name"],
                "full_name": member["full_name"],
                "email": member["email"],
                "trial_start": trial_start,
                "trial_end": trial_end_string,
                "source": "hub_checkout",
            },
        )
        return reference, plan, payment_data
    except Exception:
        execute("DELETE FROM membership_subscriptions WHERE reference = ?", (reference,))
        raise


def update_membership_subscription(reference, paystack_data, status="active"):
    data = paystack_data.get("data", {}) if isinstance(paystack_data, dict) else {}
    now = timestamp()
    execute(
        """
        UPDATE membership_subscriptions
        SET status = ?, paystack_customer_code = ?, paystack_subscription_code = ?, paystack_authorization_code = ?,
            paystack_response = ?, updated_at = ?
        WHERE reference = ?
        """,
        (
            status,
            data.get("customer", {}).get("customer_code", ""),
            data.get("subscription_code", ""),
            data.get("authorization", {}).get("authorization_code", ""),
            json.dumps(paystack_data),
            now,
            reference,
        ),
    )


def activate_membership_subscription(reference, paystack_data):
    subscription = fetch_one("SELECT * FROM membership_subscriptions WHERE reference = ?", (reference,))
    if subscription is None:
        raise ValueError("Membership subscription not found.")
    if subscription["amount_naira"] <= 0:
        return None
    data = paystack_data.get("data", {}) if isinstance(paystack_data, dict) else {}
    paystack_plan_code = subscription["paystack_plan_code"] or ensure_paystack_plan(
        subscription["plan_code"],
        subscription["plan_name"],
        subscription["amount_naira"],
    )
    if not paystack_plan_code:
        raise RuntimeError("Paystack plan code is not available.")
    authorization_code = data.get("authorization", {}).get("authorization_code", "") or subscription["paystack_authorization_code"]
    customer_code = data.get("customer", {}).get("customer_code", "") or subscription["paystack_customer_code"] or subscription["email"]
    if not authorization_code:
        raise RuntimeError("Saved authorization is required to create a recurring subscription.")
    start_date = subscription["trial_end_at"] if subscription["trial_end_at"] else None
    subscription_response = create_paystack_subscription(customer_code, paystack_plan_code, authorization_code, start_date=start_date)
    response_data = subscription_response.get("data", {}) if isinstance(subscription_response, dict) else {}
    now = timestamp()
    execute(
        """
        UPDATE membership_subscriptions
        SET status = ?, paystack_plan_code = ?, paystack_customer_code = ?, paystack_subscription_code = ?,
            paystack_authorization_code = ?, paystack_response = ?, updated_at = ?
        WHERE reference = ?
        """,
        (
            "trial" if subscription["amount_naira"] == 0 else "active",
            paystack_plan_code,
            response_data.get("customer", {}).get("customer_code", customer_code),
            response_data.get("subscription_code", ""),
            response_data.get("authorization", {}).get("authorization_code", authorization_code),
            json.dumps(subscription_response),
            now,
            reference,
        ),
    )
    execute(
        """
        UPDATE membership_subscriptions
        SET status = 'upgraded', updated_at = ?
        WHERE email = ? AND status = 'trial' AND amount_naira = 0 AND reference != ?
        """,
        (now, subscription["email"], reference),
    )
    return subscription_response


def expire_due_trial_subscriptions():
    now = timestamp()
    due_trials = fetch_all(
        """
        SELECT reference, email
        FROM membership_subscriptions
        WHERE status = 'trial'
          AND trial_end_at IS NOT NULL
          AND trial_end_at <= ?
          AND NOT EXISTS (
              SELECT 1 FROM membership_subscriptions paid
              WHERE paid.email = membership_subscriptions.email
                AND paid.status = 'active'
                AND paid.amount_naira > 0
          )
        """,
        (now,),
    )
    if not due_trials:
        return
    for subscription in due_trials:
        execute(
            """
            UPDATE membership_subscriptions
            SET status = 'expired', updated_at = ?
            WHERE reference = ?
            """,
            (now, subscription["reference"]),
        )
        execute(
            """
            UPDATE hub_members
            SET membership_tier = 'TRIAL_EXPIRED', updated_at = ?
            WHERE email = ?
            """,
            (now, subscription["email"]),
        )


def send_due_trial_reminders():
    now = timestamp()
    reminder_cutoff = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    due_trials = fetch_all(
        """
        SELECT id, full_name, email, trial_end_at
        FROM membership_subscriptions
        WHERE status = 'trial'
          AND trial_end_at IS NOT NULL
          AND trial_end_at > ?
          AND trial_end_at <= ?
          AND trial_reminder_sent_at IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM membership_subscriptions paid
              WHERE paid.email = membership_subscriptions.email
                AND paid.status = 'active'
                AND paid.amount_naira > 0
          )
        ORDER BY trial_end_at ASC
        LIMIT 10
        """,
        (now, reminder_cutoff),
    )
    if not due_trials:
        return
    plans_url = build_absolute_url(url_for("vanguard_hub"))
    login_url = build_absolute_url(url_for("hub_login"))
    for subscription in due_trials:
        claimed_at = timestamp()
        claim = execute(
            """
            UPDATE membership_subscriptions
            SET trial_reminder_sent_at = ?, updated_at = ?
            WHERE id = ? AND trial_reminder_sent_at IS NULL
            """,
            (claimed_at, claimed_at, subscription["id"]),
        )
        if claim.rowcount != 1:
            continue
        safe_name = escape(subscription["full_name"])
        safe_end = escape(subscription["trial_end_at"])
        safe_plans_url = escape(plans_url, quote=True)
        safe_login_url = escape(login_url, quote=True)
        plain_text = (
            f"Hello {subscription['full_name']},\n\n"
            f"Your free Revled Vanguard Hub access ends on {subscription['trial_end_at']} UTC.\n\n"
            "You can continue with Vanguard Plus at ₦5,000/month or Vanguard Pro at ₦10,000/month. "
            f"Review the packages here: {plans_url}\n\n"
            f"Sign in to choose your package: {login_url}"
        )
        html_text = (
            f"<p>Hello {safe_name},</p>"
            f"<p>Your free Revled Vanguard Hub access ends on <strong>{safe_end} UTC</strong>.</p>"
            "<p>You can continue with <strong>Vanguard Plus at ₦5,000/month</strong> or "
            "<strong>Vanguard Pro at ₦10,000/month</strong>.</p>"
            f"<p><a href=\"{safe_plans_url}\">Review the packages</a> or "
            f"<a href=\"{safe_login_url}\">sign in to upgrade</a>.</p>"
        )
        try:
            send_email_message(
                subscription["email"],
                "Your Vanguard Hub free access ends soon",
                plain_text,
                html_text=html_text,
            )
        except smtplib.SMTPAuthenticationError:
            app.logger.exception("SMTP rejected the configured password reset credentials.")
            if token:
                execute(
                    "UPDATE password_reset_tokens SET used_at = ? WHERE token = ?",
                    (timestamp(), token),
                )
            flash(
                "We could not send the reset email right now because the configured mailbox credentials were rejected.",
                "error",
            )
            return render_template("hub_forgot_password.html")
        except Exception:
            app.logger.exception("Failed to send Vanguard trial reminder to %s.", subscription["email"])
            execute(
                "UPDATE membership_subscriptions SET trial_reminder_sent_at = NULL, updated_at = ? WHERE id = ?",
                (timestamp(), subscription["id"]),
            )
            continue


def send_trial_welcome_email(full_name, email, trial_end_at, welcome_kit_path=None):
    """Send the Vanguard signup welcome email and attach the welcome kit when available.

    welcome_kit_path may be an absolute path to a PDF on disk. If not provided the
    WELCOME_KIT_PATH environment variable is used.
    """
    login_url = build_absolute_url(url_for("hub_login"))
    safe_name = escape(full_name)
    safe_login_url = escape(login_url, quote=True)
    plain_text = (
        f"Hello {full_name},\n\n"
        "Thank you so much for registering for Revled Vanguard! We're genuinely thrilled to have you with us.\n\n"
        "This is the beginning of something really special, and we can't wait to see what you'll accomplish. "
        "You're part of a community of ambitious young professionals and entrepreneurs, and we're honored to be part of your journey.\n\n"
        "Here's to the opportunity ahead of you.\n\n"
        "Warm regards,\n"
        "The Revled Team"
    )
    html_text = (
        f"<p>Hello {safe_name},</p>"
        "<p>Thank you so much for registering for Revled Vanguard! We're genuinely thrilled to have you with us.</p>"
        "<p>This is the beginning of something really special, and we can't wait to see what you'll accomplish. "
        "You're part of a community of ambitious young professionals and entrepreneurs, and we're honored to be part of your journey.</p>"
        "<p>Here's to the opportunity ahead of you.</p>"
        "<p>Warm regards,<br>The Revled Team</p>"
    )

    # Resolve settings at send time so hosting-panel/app settings are honored.
    username = resolve_runtime_value("REVLED_EMAIL_USERNAME", REVLED_EMAIL_USERNAME)
    password = resolve_runtime_value("REVLED_EMAIL_PASSWORD", REVLED_EMAIL_PASSWORD)
    smtp_server = resolve_runtime_value("REVLED_EMAIL_SMTP_SERVER", REVLED_EMAIL_SMTP_SERVER)
    smtp_port = int(resolve_runtime_value("REVLED_EMAIL_SMTP_PORT", str(REVLED_EMAIL_SMTP_PORT)))
    use_ssl = resolve_runtime_value("REVLED_EMAIL_USE_SSL", "1" if REVLED_EMAIL_USE_SSL else "0") != "0"
    timeout = int(resolve_runtime_value("REVLED_EMAIL_TIMEOUT", str(REVLED_EMAIL_TIMEOUT)))
    if not password:
        raise RuntimeError("REVLED_EMAIL_PASSWORD is not configured.")
    message = EmailMessage()
    message["Subject"] = "Welcome to Revled Vanguard Hub"
    message["From"] = username
    message["To"] = email
    message["Reply-To"] = username
    message.set_content(plain_text)
    message.add_alternative(html_text, subtype="html")

    # Determine welcome kit path
    kit_path = welcome_kit_path or WELCOME_KIT_PATH
    try:
        if kit_path and os.path.exists(kit_path):
            with open(kit_path, "rb") as fh:
                data = fh.read()
                message.add_attachment(
                    data,
                    maintype="application",
                    subtype="pdf",
                    filename=os.path.basename(kit_path),
                )
    except Exception:
        app.logger.exception("Failed to attach welcome kit PDF at %s", kit_path)

    # Send using existing SMTP settings
    if use_ssl:
        with smtplib.SMTP_SSL(
            smtp_server,
            smtp_port,
            timeout=timeout,
        ) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(
            smtp_server,
            smtp_port,
            timeout=timeout,
        ) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(message)


@app.before_request
def load_current_admin():
    expire_due_trial_subscriptions()
    admin_id = session.get("admin_id")
    g.current_admin = None
    if admin_id:
        g.current_admin = fetch_one("SELECT * FROM admins WHERE id = ?", (admin_id,))
    member_id = session.get("hub_member_id")
    g.current_hub_member = None
    if member_id:
        member = fetch_one("SELECT * FROM hub_members WHERE id = ? AND is_active = 1", (member_id,))
        if member is None:
            session.pop("hub_member_id", None)
        else:
            g.current_hub_member = format_hub_member(member)


@app.context_processor
def inject_globals():
    return {
        "current_year": datetime.now().year,
        "site_last_updated": current_date_label(),
        "site_transparency_summary": SITE_TRANSPARENCY_SUMMARY,
        "site_counters": SITE_COUNTERS,
        "cac_registration_number": CAC_REGISTRATION_NUMBER,
        "nonprofit_legal_name": NONPROFIT_LEGAL_NAME,
        "operating_name": OPERATING_NAME,
        "paystack_public_key": PAYSTACK_PUBLIC_KEY,
        "programs_nav": [format_program_for_template(program) for program in PROGRAMS.values()],
        "is_admin": bool(session.get("admin_id")),
        "current_admin": g.get("current_admin"),
        "is_hub_member": bool(session.get("hub_member_id")),
        "current_hub_member": g.get("current_hub_member"),
        "is_community_moderator": bool(
            g.get("current_hub_member") and community_is_moderator(g.current_hub_member["id"])
        ),
        "hub_sections": HUB_CONTENT_TYPES,
        "hub_user_types": HUB_USER_TYPES,
        "user_types": HUB_USER_TYPES,
        "brand_logo_path": url_for("static", filename=LOGO_PATH),
        "goodstack_logo_path": url_for("static", filename=GOODSTACK_LOGO_PATH),
        "contact_directory": CONTACT_DIRECTORY,
        "social_links": {
            "instagram": os.environ.get("REVLED_INSTAGRAM_URL", "https://www.instagram.com/revledfoundation/").strip(),
            "tiktok": os.environ.get("REVLED_TIKTOK_URL", "https://www.tiktok.com/@revledfoundation").strip(),
            "youtube": os.environ.get("REVLED_YOUTUBE_URL", "https://www.youtube.com/channel/UCq5_9_lchriuRnKLCFviLUg").strip(),
            "linkedin": os.environ.get("REVLED_LINKEDIN_URL","https://www.linkedin.com/company/revled-foundation?trk=blended-typeahead").strip(),
            "facebook": os.environ.get("REVLED_FACEBOOK_URL","https://www.facebook.com/share/1EY2qx2pgR/").strip(),

        },
        "faq_sections": FAQ_SECTIONS,
    }


@app.route("/")
def home():
    recent_posts = fetch_all(
        """
        SELECT id, title, slug, excerpt, published_at
        FROM blog_posts
        WHERE is_published = 1
        ORDER BY COALESCE(published_at, created_at) DESC
        LIMIT 3
        """
    )
    featured_events = fetch_all(
        """
        SELECT *
        FROM events
        WHERE is_published = 1
        ORDER BY start_date ASC
        LIMIT 3
        """
    )
    return render_template(
        "home.html",
        recent_posts=recent_posts,
        featured_events=featured_events,
        home_counters=SITE_COUNTERS["home"],
    )


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/approach")
def approach():
    return render_template("approach.html")


@app.route("/transparency")
def transparency():
    return render_template(
        "transparency.html",
        transparency_items={
            "legal_name": NONPROFIT_LEGAL_NAME,
            "operating_name": OPERATING_NAME,
            "cac_number": CAC_REGISTRATION_NUMBER,
            "location": "Lagos, Nigeria",
            "contact_email": "info@revledfoundation.org",
            "donation_use_summary": SITE_TRANSPARENCY_SUMMARY,
        },
    )


@app.route("/privacy-policy")
def privacy_policy():
    return render_template("privacy_policy.html")


@app.route("/terms-of-service")
def terms_of_service():
    return render_template("terms_of_service.html")


@app.route("/donate")
def donate():
    return render_template("donate.html", payment_public_key=get_paystack_public_key())


@app.route("/donate/callback")
def donate_callback():
    reference = request.args.get("reference", "").strip()
    if not reference:
        flash("We could not verify that donation because the reference was missing.", "error")
        return redirect(url_for("donate"))
    donation = fetch_one("SELECT * FROM donation_payments WHERE reference = ?", (reference,))
    if donation is None:
        flash("We could not find that donation record.", "error")
        return redirect(url_for("donate"))
    try:
        paystack_data = verify_paystack_transaction(reference)
        status = (paystack_data.get("data", {}).get("status") or "").lower()
        update_donation_payment(reference, paystack_data, status="success" if status == "success" else "failed")
        if status == "success":
            flash("Your donation was verified successfully. Thank you for supporting Revled.", "success")
        else:
            flash("We found your donation reference, but payment was not completed successfully.", "error")
    except Exception:
        app.logger.exception("Donation verification failed.")
        flash("We could not verify your donation right now. Please try again shortly.", "error")
    return redirect(url_for("donate", reference=reference))


@app.route("/give-resources-new-purpose")
def give_resources_new_purpose():
    return render_template("give_resources_new_purpose.html")


@app.route("/vanguard-hub")
def vanguard_hub():
    return render_template("vanguard_hub.html", membership_plans=MEMBERSHIP_PLANS, paystack_public_key=get_paystack_public_key())


@app.route("/vanguard-hub/mentor-signup", methods=["GET", "POST"])
def vanguard_mentor_signup():
    if request.method == "POST":
        try:
            application_data = {
                "full_name": request.form.get("full_name", ""),
                "email": request.form.get("email", ""),
                "phone": request.form.get("phone", ""),
                "current_role_org": request.form.get("current_role_org", ""),
                "industry": request.form.get("industry", ""),
                "other_industry": request.form.get("other_industry", ""),
                "availability": request.form.getlist("availability"),
                "frequency": request.form.get("frequency", ""),
                "availability_notes": request.form.get("availability_notes", ""),
                "topics": request.form.get("topics", ""),
            }
            record_vanguard_mentor_application(application_data)
            try:
                send_volunteer_submission_email("Vanguard", application_data)
            except Exception:
                app.logger.exception("Failed to email the Vanguard volunteer application.")
            flash("Thank you. Your Vanguard mentor signup has been submitted.", "success")
            return redirect(url_for("vanguard_mentor_signup", submitted=1))
        except ValueError as exc:
            flash(str(exc), "error")
        except sqlite3.Error:
            app.logger.exception("Failed to save Vanguard mentor application.")
            flash("We could not save your form right now. Please try again.", "error")
    return render_template("vanguard_mentor_signup.html", submitted=request.args.get("submitted") == "1")


@app.route("/catalyst/volunteer-mentor", methods=["GET", "POST"])
def catalyst_volunteer_mentor_page():
    if request.method == "POST":
        try:
            application_data = {
                "full_name": request.form.get("full_name", ""),
                "email": request.form.get("email", ""),
                "phone": request.form.get("phone", ""),
                "current_role_org": request.form.get("current_role_org", ""),
                "involvement_type": request.form.get("involvement_type", ""),
                "skill_area": request.form.get("skill_area", ""),
                "other_skill": request.form.get("other_skill", ""),
                "availability": request.form.getlist("availability"),
                "availability_notes": request.form.get("availability_notes", ""),
                "additional_notes": request.form.get("additional_notes", ""),
            }
            record_catalyst_application(application_data)
            try:
                send_volunteer_submission_email("Catalyst", application_data)
            except Exception:
                app.logger.exception("Failed to email the Catalyst volunteer application.")
            flash("Thank you. Your Catalyst application has been submitted.", "success")
            return redirect(url_for("catalyst_volunteer_mentor_page", submitted=1))
        except ValueError as exc:
            flash(str(exc), "error")
        except sqlite3.Error:
            app.logger.exception("Failed to save Catalyst application.")
            flash("We could not save your form right now. Please try again.", "error")
    return render_template("catalyst_volunteer_mentor.html", submitted=request.args.get("submitted") == "1")


@app.route("/vanguard-hub/signup", methods=["GET", "POST"])
def vanguard_hub_signup():
    if session.get("hub_member_id"):
        return redirect(url_for("hub_dashboard"))
    form_data = {
        "full_name": "",
        "email": "",
        "password": "",
        "user_type": "PROFESSIONAL",
        "plan": "trial",
    }
    if request.method == "POST":
        for key in form_data:
            form_data[key] = request.form.get(key, "").strip()
        form_data["plan"] = "trial"
        plan = get_membership_plan(form_data["plan"])
        if plan["amount_naira"] == 0:
            try:
                reference, _, _, trial_end = record_membership_subscription(form_data)
                member = fetch_one("SELECT * FROM hub_members WHERE email = ?", (form_data["email"].lower(),))
                create_admin_notification(
                    "hub-signup",
                    "New self-serve Vanguard signup",
                    f"{form_data['full_name']} started free Vanguard Hub access.",
                    "hub_members",
                    member["id"],
                )
                try:
                    send_trial_welcome_email(
                        form_data["full_name"],
                        form_data["email"].lower(),
                        trial_end,
                        welcome_kit_path=os.environ.get("WELCOME_KIT_PATH", WELCOME_KIT_PATH),
                    )
                except Exception:
                    app.logger.exception(
                        "Failed to send Vanguard signup welcome email to %s.",
                        form_data["email"].lower(),
                    )
                    flash(
                        "Your account was created, but we could not send the welcome email. "
                        "Please check your inbox later or contact support.",
                        "error",
                    )
                session["hub_member_id"] = member["id"]
                # make the welcome kit available for immediate download in the dashboard
                try:
                    session["welcome_kit_available"] = True
                except Exception:
                    pass
                flash(
                    "Welcome to the Vanguard Hub. Your free access is active.",
                    "success",
                )
                return redirect(url_for("hub_dashboard", reference=reference))
            except ValueError as exc:
                flash(str(exc), "error")
        else:
            try:
                reference, chosen_plan, trial_start, trial_end = record_membership_subscription(form_data)
                if not PAYSTACK_SECRET_KEY:
                    flash("Your membership has been recorded, but online checkout is not configured yet.", "success")
                    return redirect(url_for("hub_login"))
                callback_url = build_absolute_url(url_for("vanguard_hub_callback"))
                payment_data = initialize_paystack_transaction(
                    form_data["email"],
                    chosen_plan["amount_naira"],
                    reference,
                    callback_url,
                    {
                        "payment_type": "membership",
                        "plan_code": chosen_plan["plan_code"],
                        "plan_name": chosen_plan["name"],
                        "full_name": form_data["full_name"],
                        "email": form_data["email"],
                        "source": "website",
                        "trial_start": trial_start,
                        "trial_end": trial_end,
                    },
                )
                auth_url = payment_data.get("data", {}).get("authorization_url")
                if auth_url:
                    return redirect(auth_url)
                flash("We could not start the membership payment just now.", "error")
            except ValueError as exc:
                flash(str(exc), "error")
            except Exception:
                app.logger.exception("Membership initialization failed.")
                flash("We could not start the membership payment just now.", "error")
    return render_template("vanguard_hub_signup.html", form_data=form_data, membership_plans=MEMBERSHIP_PLANS)


@app.get("/vanguard-hub/checkout/<plan_key>")
def vanguard_hub_public_checkout(plan_key):
    plan = get_membership_plan(plan_key)
    if plan["amount_naira"] <= 0:
        return redirect(url_for("vanguard_hub_signup", plan="trial"))
    if session.get("hub_member_id"):
        return redirect(url_for("hub_membership_checkout", plan_key=plan_key))
    return redirect(url_for("vanguard_hub_signup", plan=plan_key))


@app.route("/vanguard-hub/callback")
def vanguard_hub_callback():
    reference = request.args.get("reference", "").strip()
    if not reference:
        flash("We could not verify that membership payment because the reference was missing.", "error")
        return redirect(url_for("vanguard_hub"))
    subscription = fetch_one("SELECT * FROM membership_subscriptions WHERE reference = ?", (reference,))
    if subscription is None:
        flash("We could not find that membership record.", "error")
        return redirect(url_for("vanguard_hub"))
    try:
        paystack_data = verify_paystack_transaction(reference)
        status = (paystack_data.get("data", {}).get("status") or "").lower()
        update_membership_subscription(reference, paystack_data, status="active" if status == "success" else "failed")
        if status == "success":
            if subscription["amount_naira"] > 0:
                activate_membership_subscription(reference, paystack_data)
            execute(
                "UPDATE hub_members SET membership_tier = ?, updated_at = ? WHERE email = ?",
                ("FULL_ACCESS" if subscription["amount_naira"] else "ESSENTIAL", timestamp(), subscription["email"]),
            )
            flash("Your Vanguard membership is active.", "success")
        else:
            flash("We found your membership reference, but payment was not completed successfully.", "error")
    except Exception:
        app.logger.exception("Membership verification failed.")
        flash("We could not verify your membership payment right now. Please try again shortly.", "error")
    return redirect(url_for("vanguard_hub"))


@app.route("/api/payments/donations/initialize", methods=["POST"])
def api_initialize_donation():
    form_data = request.get_json(silent=True) or request.form.to_dict()
    try:
        reference = record_donation_payment(form_data)
        if not PAYSTACK_SECRET_KEY:
            return {
                "ok": True,
                "reference": reference,
                "authorization_url": "",
                "message": "Donation recorded. Online payment is not configured yet.",
            }
        callback_url = build_absolute_url(url_for("donate_callback"))
        payment_data = initialize_paystack_transaction(
            form_data.get("donor_email", ""),
            parse_amount(form_data.get("amount")),
            reference,
            callback_url,
            {
                "payment_type": "donation",
                "donor_name": form_data.get("donor_name", "").strip(),
                "donor_email": form_data.get("donor_email", "").strip().lower(),
                "message": (form_data.get("message") or "").strip(),
                "source": "website",
            },
        )
        return {
            "ok": True,
            "reference": reference,
            "authorization_url": payment_data.get("data", {}).get("authorization_url", ""),
        }
    except ValueError as exc:
        return {"ok": False, "message": str(exc)}, 400
    except Exception:
        app.logger.exception("Donation initialization failed.")
        return {"ok": False, "message": "Could not start donation payment."}, 500


@app.route("/api/payments/memberships/initialize", methods=["POST"])
def api_initialize_membership():
    form_data = request.get_json(silent=True) or request.form.to_dict()
    try:
        reference, plan, trial_start, trial_end = record_membership_subscription(form_data)
        if plan["amount_naira"] == 0:
            return {
                "ok": True,
                "reference": reference,
                "authorization_url": "",
                "trial_start": trial_start,
                "trial_end": trial_end,
            }
        if not PAYSTACK_SECRET_KEY:
            return {
                "ok": True,
                "reference": reference,
                "authorization_url": "",
                "trial_start": trial_start,
                "trial_end": trial_end,
                "message": "Membership recorded. Online payment is not configured yet.",
            }
        callback_url = build_absolute_url(url_for("vanguard_hub_callback"))
        payment_data = initialize_paystack_transaction(
            form_data.get("email", ""),
            plan["amount_naira"],
            reference,
            callback_url,
            {
                "payment_type": "membership",
                "plan_code": plan["plan_code"],
                "plan_name": plan["name"],
                "full_name": form_data.get("full_name", "").strip(),
                "email": form_data.get("email", "").strip().lower(),
                "trial_start": trial_start,
                "trial_end": trial_end,
                "source": "website",
            },
        )
        return {
            "ok": True,
            "reference": reference,
            "authorization_url": payment_data.get("data", {}).get("authorization_url", ""),
            "trial_start": trial_start,
            "trial_end": trial_end,
        }
    except ValueError as exc:
        return {"ok": False, "message": str(exc)}, 400
    except Exception:
        app.logger.exception("Membership initialization failed.")
        return {"ok": False, "message": "Could not start membership flow."}, 500


@app.get("/hub/membership/checkout/<plan_key>")
@hub_login_required
def hub_membership_checkout(plan_key):
    member = g.current_hub_member
    try:
        _, plan, payment_data = start_membership_checkout(member, plan_key)
        authorization_url = payment_data.get("data", {}).get("authorization_url", "")
        if not authorization_url:
            flash("We could not open online checkout right now. Please try again.", "error")
            return redirect(url_for("hub_dashboard"))
        return redirect(authorization_url)
    except ValueError as exc:
        flash(str(exc), "error")
    except Exception:
        app.logger.exception("Membership checkout initialization failed.")
        flash("Could not start online checkout right now.", "error")
    return redirect(url_for("hub_dashboard"))


@app.route("/api/payments/verify", methods=["GET", "POST"])
def api_verify_payment():
    payload = request.get_json(silent=True) or request.form.to_dict() or request.args.to_dict()
    reference = (payload.get("reference") or "").strip()
    payment_type = (payload.get("payment_type") or "").strip().lower()
    if not reference:
        return {"ok": False, "message": "Reference is required."}, 400
    try:
        paystack_data = verify_paystack_transaction(reference)
        status = (paystack_data.get("data", {}).get("status") or "").lower()
        if payment_type == "membership":
            update_membership_subscription(reference, paystack_data, status="active" if status == "success" else "failed")
            if status == "success":
                subscription = fetch_one("SELECT amount_naira FROM membership_subscriptions WHERE reference = ?", (reference,))
                if subscription and subscription["amount_naira"] > 0:
                    activate_membership_subscription(reference, paystack_data)
        else:
            update_donation_payment(reference, paystack_data, status="success" if status == "success" else "failed")
        return {"ok": True, "status": status, "reference": reference}
    except Exception:
        app.logger.exception("Payment verification failed.")
        return {"ok": False, "message": "Could not verify payment."}, 500


@app.route("/paystack/webhook", methods=["POST"])
def paystack_webhook():
    if not PAYSTACK_SECRET_KEY:
        return "", 503
    signature = request.headers.get("X-Paystack-Signature", "")
    payload = request.get_data() or b""
    expected = hmac.new(PAYSTACK_SECRET_KEY.encode("utf-8"), payload, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return "", 401
    try:
        event = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError:
        return "", 400

    event_type = (event.get("event") or "").strip().lower()
    data = event.get("data", {}) if isinstance(event, dict) else {}
    reference = (data.get("reference") or data.get("metadata", {}).get("reference") or "").strip()

    try:
        if event_type in {"charge.success", "invoice.payment_failed"} and reference:
            payment_type = (data.get("metadata", {}).get("payment_type") or "").strip().lower()
            membership_record = fetch_one("SELECT amount_naira FROM membership_subscriptions WHERE reference = ?", (reference,))
            if payment_type == "membership" or membership_record:
                update_membership_subscription(reference, event, status="active" if event_type == "charge.success" else "failed")
                if event_type == "charge.success" and membership_record and membership_record["amount_naira"] > 0:
                    activate_membership_subscription(reference, event)
        elif event_type in {"subscription.disable", "subscription.not_renew"}:
            subscription_code = (data.get("subscription_code") or "").strip()
            if subscription_code:
                execute(
                    """
                    UPDATE membership_subscriptions
                    SET status = 'cancelled', cancellation_at = ?, updated_at = ?
                    WHERE paystack_subscription_code = ?
                    """,
                    (timestamp(), timestamp(), subscription_code),
                )
        elif event_type == "subscription.create" and reference:
            update_membership_subscription(reference, event, status="active")
        elif event_type == "invoice.create":
            subscription_code = (data.get("subscription_code") or "").strip()
            if subscription_code:
                execute(
                    """
                    UPDATE membership_subscriptions
                    SET next_billing_at = ?, updated_at = ?
                    WHERE paystack_subscription_code = ?
                    """,
                    (data.get("due_date") or timestamp(), timestamp(), subscription_code),
                )
    except Exception:
        app.logger.exception("Paystack webhook processing failed.")
        return "", 500
    return "", 200


@app.route("/api/payments/memberships/cancel", methods=["POST"])
def api_cancel_membership():
    payload = request.get_json(silent=True) or request.form.to_dict()
    reference = (payload.get("reference") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    if not reference or not email:
        return {"ok": False, "message": "Reference and email are required."}, 400
    subscription = fetch_one(
        "SELECT * FROM membership_subscriptions WHERE reference = ? AND email = ?",
        (reference, email),
    )
    if subscription is None:
        return {"ok": False, "message": "Subscription not found."}, 404
    execute(
        """
        UPDATE membership_subscriptions
        SET status = 'cancelled', cancellation_at = ?, updated_at = ?
        WHERE reference = ?
        """,
        (timestamp(), timestamp(), reference),
    )
    execute(
        "UPDATE hub_members SET membership_tier = 'ESSENTIAL', updated_at = ? WHERE email = ?",
        (timestamp(), email),
    )
    return {"ok": True, "message": "Membership cancelled."}


@app.route("/faq")
def faq():
    return render_template("faq.html", faq_sections=FAQ_SECTIONS)


@app.route("/programs")
def programs():
    return redirect(url_for("program_detail", program_slug="roots"))


@app.route("/programs/<program_slug>")
def program_detail(program_slug):
    program = format_program_for_template(get_program(program_slug))
    related_events = fetch_all(
        """
        SELECT *
        FROM events
        WHERE is_published = 1 AND (program_slug = ? OR program_slug IS NULL)
        ORDER BY start_date ASC
        LIMIT 4
        """,
        (program_slug,),
    )
    if program["show_workbooks"]:
        workbooks = fetch_all(
            """
            SELECT *
            FROM resources
            WHERE is_published = 1
              AND resource_type IN ('book', 'workbook', 'guide')
              AND audience IN ('all', 'parents', ?)
            ORDER BY created_at DESC
            LIMIT 4
            """,
            (program_slug,),
        )
    else:
        workbooks = []
    return render_template("program_detail.html", program=program, related_events=related_events, workbooks=workbooks)


@app.route("/programs/catalyst/apply", methods=["POST"])
def catalyst_application():
    try:
        record_catalyst_application({
            "full_name": request.form.get("Full name", ""),
            "email": request.form.get("Email", ""),
            "phone": request.form.get("Phone", ""),
            "current_role_org": request.form.get("Current role and organisation", ""),
            "involvement_type": request.form.get("Type of involvement", ""),
            "skill_area": request.form.get("Skill area", ""),
            "other_skill": request.form.get("Other skill", ""),
            "availability": request.form.getlist("Availability"),
            "availability_notes": request.form.get("Availability notes", ""),
            "additional_notes": request.form.get("Additional notes", ""),
        })
        if request.headers.get("X-Requested-With") == "fetch":
            return {"status": "saved"}, 201
        flash("Thank you. Your Catalyst application has been submitted.", "success")
        return redirect(url_for("program_detail", program_slug="catalyst", submitted=1) + "#catalyst-application-form")
    except ValueError as exc:
        if request.headers.get("X-Requested-With") == "fetch":
            return {"error": str(exc)}, 400
        flash(str(exc), "error")
    except sqlite3.Error:
        app.logger.exception("Failed to save Catalyst application.")
        if request.headers.get("X-Requested-With") == "fetch":
            return {"error": "We could not save your form right now. Please try again."}, 500
        flash("We could not save your form right now. Please try again.", "error")
    return redirect(url_for("program_detail", program_slug="catalyst") + "#catalyst-application-form")


@app.route("/programs/<program_slug>/register", methods=["GET", "POST"])
def program_register(program_slug):
    program = get_program(program_slug)
    form_data = {
        "full_name": "",
        "email": "",
        "phone": "",
        "applicant_age": "",
        "city": "",
        "state_region": "",
        "guardian_name": "",
        "guardian_phone": "",
        "school_or_work": "",
        "goals": "",
        "interest_reason": "",
        "preferred_start": "",
    }

    if request.method == "POST":
        for key in form_data:
            form_data[key] = request.form.get(key, "").strip()

        required_fields = [
            "full_name",
            "email",
            "phone",
            "applicant_age",
            "city",
            "state_region",
            "goals",
            "interest_reason",
        ]
        missing = [field for field in required_fields if not form_data[field]]

        if missing:
            flash("Please complete all required registration fields.", "error")
        else:
            now = timestamp()
            cursor = execute(
                """
                INSERT INTO program_registrations (
                    program_slug, program_name, full_name, email, phone, applicant_age, city, state_region,
                    guardian_name, guardian_phone, school_or_work, goals, interest_reason, preferred_start,
                    follow_up_status, follow_up_notes, admin_notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', '', '', ?, ?)
                """,
                (
                    program["slug"],
                    program["name"],
                    form_data["full_name"],
                    form_data["email"],
                    form_data["phone"],
                    form_data["applicant_age"],
                    form_data["city"],
                    form_data["state_region"],
                    form_data["guardian_name"],
                    form_data["guardian_phone"],
                    form_data["school_or_work"],
                    form_data["goals"],
                    form_data["interest_reason"],
                    form_data["preferred_start"],
                    now,
                    now,
                ),
            )
            create_admin_notification(
                "registration",
                f"New {program['name']} registration",
                f"{form_data['full_name']} submitted a registration for {program['name']}.",
                "program_registrations",
                cursor.lastrowid,
            )
            try:
                send_registration_confirmation_email(
                    form_data["full_name"],
                    form_data["email"].lower(),
                    program["name"],
                )
            except Exception:
                app.logger.exception("Failed to send registration confirmation email.")
            flash(f"Your registration for {program['name']} has been received. Our team will follow up soon.", "success")
            return redirect(url_for("program_register", program_slug=program_slug))

    return render_template("program_register.html", program=format_program_for_template(program), form_data=form_data)


@app.route("/programs/<program_slug>/enquiry/<enquiry_type>", methods=["GET", "POST"])
def programme_enquiry(program_slug, enquiry_type):
    program = format_program_for_template(get_program(program_slug))
    enquiry_type = enquiry_type.strip()
    enquiry_meta = {
        "school-partnership": {
            "title": f"Bring {program['name']} to Your School",
            "subtitle": "Tell us about your institution, target students, and what you want Revled to run.",
        },
        "sponsor-cohort": {
            "title": f"Sponsor a {program['name']} Cohort",
            "subtitle": "Share your organisation details and the kind of impact partnership you are exploring.",
        },
        "join-launchpad": {
            "title": "Join Revled Vanguard",
            "subtitle": "Get free access to the Vanguard community, newsletters, and upcoming opportunities.",
        },
    }.get(enquiry_type)

    if enquiry_meta is None:
        abort(404)

    form_data = {
        "contact_name": "",
        "email": "",
        "phone": "",
        "organization": "",
        "child_name": "",
        "child_age": "",
        "location": "",
        "preferred_term": "",
        "budget_range": "",
        "message": "",
    }

    if request.method == "POST":
        for key in form_data:
            form_data[key] = request.form.get(key, "").strip()
        required = ["contact_name", "email", "phone", "message"]
        if enquiry_type == "join-launchpad":
            required = ["contact_name", "email", "phone", "location", "message"]
        if any(not form_data[field] for field in required):
            flash("Please complete the required enquiry fields.", "error")
        else:
            now = timestamp()
            cursor = execute(
                """
                INSERT INTO enquiries (
                    enquiry_type, program_slug, program_name, contact_name, email, phone, organization,
                    child_name, child_age, location, preferred_term, budget_range, message, status, admin_notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', '', ?, ?)
                """,
                (
                    enquiry_type,
                    program["slug"],
                    program["name"],
                    form_data["contact_name"],
                    form_data["email"],
                    form_data["phone"],
                    form_data["organization"],
                    form_data["child_name"],
                    form_data["child_age"],
                    form_data["location"],
                    form_data["preferred_term"],
                    form_data["budget_range"],
                    form_data["message"],
                    now,
                    now,
                ),
            )
            create_admin_notification(
                "enquiry",
                f"New {enquiry_type} enquiry",
                f"{form_data['contact_name']} submitted a {enquiry_type} enquiry for {program['name']}.",
                "enquiries",
                cursor.lastrowid,
            )
            programme_contact = CONTACT_DIRECTORY["programmes"].get(program["slug"])
            if programme_contact:
                email_subject = f"New {program['name']} enquiry"
                email_body = (
                    f"Programme: {program['name']}\n"
                    f"Enquiry type: {enquiry_type}\n"
                    f"Contact name: {form_data['contact_name']}\n"
                    f"Email: {form_data['email']}\n"
                    f"Phone: {form_data['phone']}\n"
                    f"Organization: {form_data['organization']}\n"
                    f"Location: {form_data['location']}\n"
                    f"Preferred term: {form_data['preferred_term']}\n"
                    f"Budget range: {form_data['budget_range']}\n\n"
                    f"Message:\n{form_data['message']}"
                )
                try:
                    send_email_message(programme_contact["email"], email_subject, email_body)
                except Exception:
                    app.logger.exception("Failed to send programme enquiry email.")
            flash("Your enquiry has been sent. The Revled team will follow up shortly.", "success")
            return redirect(url_for("programme_enquiry", program_slug=program_slug, enquiry_type=enquiry_type))

    return render_template("enquiry_form.html", program=program, enquiry_type=enquiry_type, enquiry_meta=enquiry_meta, form_data=form_data)


@app.route("/events")
def events_list():
    events = fetch_all(
        """
        SELECT *
        FROM events
        WHERE is_published = 1
        ORDER BY start_date ASC
        """
    )
    return render_template("events.html", events=events)


@app.route("/events/<slug>", methods=["GET", "POST"])
def event_detail(slug):
    event = fetch_one(
        """
        SELECT e.*, COALESCE(SUM(er.seat_count), 0) AS seats_reserved
        FROM events e
        LEFT JOIN event_registrations er ON er.event_id = e.id
        WHERE e.slug = ? AND e.is_published = 1
        GROUP BY e.id
        """,
        (slug,),
    )
    if event is None:
        abort(404)

    form_data = {"full_name": "", "email": "", "phone": "", "organization": "", "notes": "", "seat_count": "1"}
    capacity = get_event_capacity(event)
    if request.method == "POST":
        if not event["requires_registration"]:
            flash("This event does not require a registration form.", "error")
            return redirect(url_for("event_detail", slug=slug))
        for key in form_data:
            form_data[key] = request.form.get(key, "").strip()
        seat_count = max(1, coerce_int(form_data["seat_count"], 1))
        if not all([form_data["full_name"], form_data["email"], form_data["phone"]]):
            flash("Please complete your name, email, and phone number to register.", "error")
        elif capacity["is_full"]:
            flash("This event is already fully reserved.", "error")
        elif capacity["seats_remaining"] is not None and seat_count > capacity["seats_remaining"]:
            flash(f"Only {capacity['seats_remaining']} seat(s) remain for this event.", "error")
        else:
            cursor = execute(
                """
                INSERT INTO event_registrations (event_id, full_name, email, phone, organization, notes, seat_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    form_data["full_name"],
                    form_data["email"],
                    form_data["phone"],
                    form_data["organization"],
                    form_data["notes"],
                    seat_count,
                    timestamp(),
                ),
            )
            create_admin_notification(
                "event-registration",
                f"New event signup for {event['title']}",
                f"{form_data['full_name']} reserved {seat_count} seat(s) for {event['title']}.",
                "event_registrations",
                cursor.lastrowid,
            )
            flash(f"You have successfully reserved {seat_count} seat(s) for this event.", "success")
            return redirect(url_for("event_detail", slug=slug))

    registrations_count = fetch_one("SELECT COUNT(*) AS total FROM event_registrations WHERE event_id = ?", (event["id"],))["total"]
    return render_template(
        "event_detail.html",
        event=event,
        form_data=form_data,
        registrations_count=registrations_count,
        capacity=capacity,
        program=PROGRAMS.get(event["program_slug"]),
    )


@app.route("/impact")
def impact():
    return render_template("impact.html")


@app.route("/get-involved")
def get_involved():
    partnership_events = fetch_all(
        """
        SELECT *
        FROM events
        WHERE is_published = 1
        ORDER BY start_date ASC
        LIMIT 3
        """
    )
    return render_template("get-involved.html", partnership_events=partnership_events)


@app.route("/resources")
def resources():
    resources = fetch_all(
        """
        SELECT *
        FROM resources
        WHERE is_published = 1
        ORDER BY resource_type ASC, created_at DESC
        """
    )
    return render_template("resources.html", resources=resources)


@app.route("/consultation/book", methods=["GET", "POST"])
def book_consultation():
    form_data = {
        "full_name": "",
        "email": "",
        "phone": "",
        "organization": "",
        "consultation_type": "",
        "preferred_date": "",
        "message": "",
    }
    if request.method == "POST":
        for key in form_data:
            form_data[key] = request.form.get(key, "").strip()
        required = ["full_name", "email", "phone", "consultation_type", "message"]
        if any(not form_data[field] for field in required):
            flash("Please complete the required consultation fields.", "error")
        else:
            now = timestamp()
            cursor = execute(
                """
                INSERT INTO consultation_bookings (
                    full_name, email, phone, organization, consultation_type, preferred_date,
                    message, status, admin_notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'new', '', ?, ?)
                """,
                (
                    form_data["full_name"],
                    form_data["email"],
                    form_data["phone"],
                    form_data["organization"],
                    form_data["consultation_type"],
                    form_data["preferred_date"],
                    form_data["message"],
                    now,
                    now,
                ),
            )
            create_admin_notification(
                "consultation",
                "New consultation request",
                f"{form_data['full_name']} requested a {form_data['consultation_type']} consultation.",
                "consultation_bookings",
                cursor.lastrowid,
            )
            flash("Your consultation request has been received. We will follow up with available slots.", "success")
            return redirect(url_for("book_consultation"))

    return render_template("consultation_book.html", form_data=form_data)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    form_data = {"name": "", "email": "", "subject": "", "message": ""}
    if request.method == "POST":
        for key in form_data:
            form_data[key] = request.form.get(key, "").strip()

        if not all(form_data.values()):
            flash("Please fill in all fields.", "error")
        elif len(form_data["message"]) < 10:
            flash("Message must be at least 10 characters.", "error")
        else:
            now = timestamp()
            cursor = execute(
                """
                INSERT INTO contact_messages (full_name, email, subject, message, status, admin_notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'new', '', ?, ?)
                """,
                (
                    form_data["name"],
                    form_data["email"],
                    form_data["subject"],
                    form_data["message"],
                    now,
                    now,
                ),
            )
            create_admin_notification(
                "contact",
                f"New contact message: {form_data['subject']}",
                f"{form_data['name']} sent a contact message.",
                "contact_messages",
                cursor.lastrowid,
            )
            flash(f"Thank you {form_data['name']}! We'll get back to you soon.", "success")
            return redirect(url_for("contact"))

    return render_template("contact.html", form_data=form_data, faq_sections=FAQ_SECTIONS)


@app.route("/blog")
def blog_list():
    posts = fetch_all(
        """
        SELECT
            bp.*,
            COUNT(DISTINCT bc.id) AS comment_count,
            COUNT(DISTINCT bl.id) AS like_count
        FROM blog_posts bp
        LEFT JOIN blog_comments bc ON bc.post_id = bp.id AND bc.is_approved = 1
        LEFT JOIN blog_likes bl ON bl.post_id = bp.id
        WHERE bp.is_published = 1
        GROUP BY bp.id
        ORDER BY COALESCE(bp.published_at, bp.created_at) DESC
        """
    )
    featured_post = posts[0] if posts else None
    return render_template("blog_list.html", posts=posts, featured_post=featured_post)


@app.route("/blog/<slug>")
def blog_detail(slug):
    post = fetch_one(
        """
        SELECT
            bp.*,
            COUNT(DISTINCT bc.id) AS comment_count,
            COUNT(DISTINCT bl.id) AS like_count
        FROM blog_posts bp
        LEFT JOIN blog_comments bc ON bc.post_id = bp.id AND bc.is_approved = 1
        LEFT JOIN blog_likes bl ON bl.post_id = bp.id
        WHERE bp.slug = ? AND bp.is_published = 1
        GROUP BY bp.id
        """,
        (slug,),
    )
    if post is None:
        abort(404)

    comments = fetch_all(
        """
        SELECT *
        FROM blog_comments
        WHERE post_id = ? AND is_approved = 1
        ORDER BY created_at DESC
        """,
        (post["id"],),
    )

    visitor_token = session.get("visitor_token")
    liked = False
    if visitor_token:
        liked = fetch_one(
            "SELECT id FROM blog_likes WHERE post_id = ? AND visitor_token = ?",
            (post["id"], visitor_token),
        ) is not None

    return render_template(
        "blog_detail.html",
        post=post,
        comments=comments,
        liked=liked,
        article_content_html=format_blog_content_html(post["content"]),
    )


@app.post("/blog/<slug>/comment")
def blog_comment(slug):
    post = fetch_one("SELECT id FROM blog_posts WHERE slug = ? AND is_published = 1", (slug,))
    if post is None:
        abort(404)
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    content = request.form.get("content", "").strip()
    if not all([name, email, content]):
        flash("Please complete your name, email, and comment before submitting.", "error")
    else:
        execute(
            """
            INSERT INTO blog_comments (post_id, name, email, content, is_approved, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (post["id"], name, email, content, timestamp()),
        )
        flash("Your comment has been posted.", "success")
    return redirect(url_for("blog_detail", slug=slug))


@app.post("/blog/<slug>/like")
def blog_like(slug):
    post = fetch_one("SELECT id FROM blog_posts WHERE slug = ? AND is_published = 1", (slug,))
    if post is None:
        abort(404)
    visitor_token = session.get("visitor_token")
    if not visitor_token:
        visitor_token = secrets.token_hex(16)
        session["visitor_token"] = visitor_token
    existing = fetch_one(
        "SELECT id FROM blog_likes WHERE post_id = ? AND visitor_token = ?",
        (post["id"], visitor_token),
    )
    if existing is None:
        execute(
            "INSERT INTO blog_likes (post_id, visitor_token, created_at) VALUES (?, ?, ?)",
            (post["id"], visitor_token, timestamp()),
        )
        flash("You liked this story.", "success")
    else:
        flash("You already liked this story.", "error")
    return redirect(url_for("blog_detail", slug=slug))


@app.route("/hub/signup", methods=["GET", "POST"])
def hub_signup():
    status_code = 307 if request.method == "POST" else 302
    return redirect(url_for("vanguard_hub_signup"), code=status_code)


@app.route("/hub/<content_type>/<int:item_id>")
@hub_login_required
def hub_content_detail(content_type, item_id):
    if content_type not in hub_detail_types():
        abort(404)
    member = g.current_hub_member
    item = get_hub_content_item_for_member(item_id, member, content_type=content_type)
    joined = is_member_joined_to_content(item_id, member["id"])
    messages = []
    if joined:
        messages = fetch_hub_messages(item_id)
    return render_template(
        "hub_content_detail.html",
        member=member,
        config=get_hub_content_config(content_type),
        content_type=content_type,
        item=item,
        joined=joined,
        membership_count=count_hub_memberships(item_id),
        messages=messages,
        active_section=content_type,
    )


@app.post("/hub/<content_type>/<int:item_id>/join")
@hub_login_required
def hub_content_join(content_type, item_id):
    if content_type not in hub_detail_types():
        abort(404)
    member = g.current_hub_member
    item = get_hub_content_item_for_member(item_id, member, content_type=content_type)
    if not is_member_joined_to_content(item_id, member["id"]):
        execute(
            "INSERT INTO hub_content_memberships (content_id, member_id, joined_at) VALUES (?, ?, ?)",
            (item_id, member["id"], timestamp()),
        )
        flash(f"You joined {item['title']}.", "success")
    else:
        flash(f"You are already part of {item['title']}.", "success")
    return redirect(url_for("hub_content_detail", content_type=content_type, item_id=item_id))


@app.post("/hub/<content_type>/<int:item_id>/messages")
@hub_login_required
def hub_content_message(content_type, item_id):
    if content_type not in hub_detail_types():
        abort(404)
    member = g.current_hub_member
    item = get_hub_content_item_for_member(item_id, member, content_type=content_type)
    if not is_member_joined_to_content(item_id, member["id"]):
        flash(f"Join {item['title']} before posting.", "error")
        return redirect(url_for("hub_content_detail", content_type=content_type, item_id=item_id))
    message = request.form.get("message", "").strip()
    if not message:
        flash("Write a message before sending it.", "error")
    else:
        execute(
            "INSERT INTO hub_messages (content_id, member_id, message, created_at) VALUES (?, ?, ?, ?)",
            (item_id, member["id"], message, timestamp()),
        )
        flash("Message sent.", "success")
    return redirect(url_for("hub_content_detail", content_type=content_type, item_id=item_id))


@app.route("/hub/resources/<int:item_id>/view")
@hub_login_required
def hub_resource_view(item_id):
    member = g.current_hub_member
    item = get_hub_content_item_for_member(item_id, member)
    if item["content_type"] != "resources" or not item.get("uploaded_file"):
        return redirect(item.get("resource_link") or url_for("hub_resources"))
    extension = os.path.splitext(item["uploaded_file_name"] or item["uploaded_file"])[1].lower().lstrip(".")
    file_kind = "document"
    if extension in {"mp4", "webm", "mov"}:
        file_kind = "video"
    elif extension in {"png", "jpg", "jpeg"}:
        file_kind = "image"
    elif extension == "pdf":
        file_kind = "pdf"
    return render_template("hub_resource_view.html", item=item, member=member, file_kind=file_kind)


@app.route("/hub/resources/<int:item_id>/stream")
@hub_login_required
def hub_resource_stream(item_id):
    member = g.current_hub_member
    item = get_hub_content_item_for_member(item_id, member)
    if item["content_type"] != "resources" or not item.get("uploaded_file"):
        abort(404)
    file_path = os.path.join(HUB_UPLOAD_DIR, item["uploaded_file"])
    if not os.path.exists(file_path):
        abort(404)
    mimetype = mimetypes.guess_type(item["uploaded_file_name"] or item["uploaded_file"])[0] or "application/octet-stream"
    response = send_file(file_path, mimetype=mimetype, as_attachment=False, download_name=item["uploaded_file_name"] or item["uploaded_file"], conditional=True)
    response.headers["Content-Disposition"] = f'inline; filename="{item["uploaded_file_name"] or item["uploaded_file"]}"'
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.route("/hub/resources/<int:item_id>/download")
@hub_login_required
def hub_resource_download(item_id):
    member = g.current_hub_member
    item = get_hub_content_item_for_member(item_id, member, content_type="resources")
    file_path = os.path.join(HUB_UPLOAD_DIR, item["uploaded_file"])
    if not os.path.isfile(file_path):
        abort(404)
    mimetype = mimetypes.guess_type(item["uploaded_file_name"] or item["uploaded_file"])[0] or "application/octet-stream"
    response = send_file(
        file_path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=item["uploaded_file_name"] or item["uploaded_file"],
        conditional=True,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/community/posts")
@community_member_required
def community_posts_api():
    page = max(1, coerce_int(request.args.get("page", "1"), 1))
    limit = max(1, min(50, coerce_int(request.args.get("limit", "20"), 20)))
    search = request.args.get("q", "").strip()
    offset = (page - 1) * limit
    where = ["cp.is_deleted = 0", "cp.is_hidden = 0"]
    params = []
    if search:
        where.append("(cp.content LIKE ? OR hm.full_name LIKE ?)")
        pattern = f"%{search}%"
        params.extend([pattern, pattern])
    where_sql = " AND ".join(where)
    total = fetch_one(
        f"""
        SELECT COUNT(*) AS total FROM community_posts cp
        JOIN hub_members hm ON hm.id = cp.user_id
        WHERE {where_sql}
        """,
        tuple(params),
    )["total"]
    rows = fetch_all(
        f"""
        SELECT cp.* FROM community_posts cp
        JOIN hub_members hm ON hm.id = cp.user_id
        WHERE {where_sql}
        ORDER BY cp.is_pinned DESC, cp.created_at DESC, cp.id DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [limit, offset]),
    )
    return jsonify({
        "posts": [community_post_payload(row) for row in rows],
        "page": page,
        "limit": limit,
        "total": total,
        "has_more": offset + len(rows) < total,
    })


@app.post("/community/posts")
@community_member_required
def community_create_post_api():
    data = request.get_json(silent=True) or request.form
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "Write something before publishing."}), 400
    if len(content) > 5000:
        return jsonify({"error": "Posts must be 5,000 characters or fewer."}), 400
    member_id = g.current_hub_member["id"]
    duplicate = fetch_one(
        """
        SELECT id FROM community_posts
        WHERE user_id = ? AND content = ? AND is_deleted = 0
          AND created_at >= datetime('now', '-10 seconds')
        LIMIT 1
        """,
        (member_id, content),
    )
    if duplicate:
        return jsonify({"error": "That post was already published."}), 409
    now = timestamp()
    cursor = execute(
        """
        INSERT INTO community_posts (user_id, content, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (member_id, content, now, now),
    )
    row = fetch_one("SELECT * FROM community_posts WHERE id = ?", (cursor.lastrowid,))
    return jsonify({"post": community_post_payload(row)}), 201


@app.get("/community/posts/<int:post_id>")
@community_member_required
def community_post_detail_api(post_id):
    row = fetch_one(
        "SELECT * FROM community_posts WHERE id = ? AND is_deleted = 0 AND is_hidden = 0",
        (post_id,),
    )
    if row is None:
        return jsonify({"error": "Post not found."}), 404
    return jsonify({"post": community_post_payload(row, include_replies=True)})


@app.patch("/community/posts/<int:post_id>")
@community_member_required
def community_edit_post_api(post_id):
    row = fetch_one("SELECT * FROM community_posts WHERE id = ? AND is_deleted = 0", (post_id,))
    if row is None:
        return jsonify({"error": "Post not found."}), 404
    if not community_content_authorized(row, g.current_hub_member["id"]):
        return jsonify({"error": "You cannot edit this post."}), 403
    content = ((request.get_json(silent=True) or {}).get("content") or "").strip()
    if not content or len(content) > 5000:
        return jsonify({"error": "Post content must be between 1 and 5,000 characters."}), 400
    execute("UPDATE community_posts SET content = ?, updated_at = ? WHERE id = ?", (content, timestamp(), post_id))
    return jsonify({"post": community_post_payload(fetch_one("SELECT * FROM community_posts WHERE id = ?", (post_id,)))})


@app.delete("/community/posts/<int:post_id>")
@community_member_required
def community_delete_post_api(post_id):
    row = fetch_one("SELECT * FROM community_posts WHERE id = ? AND is_deleted = 0", (post_id,))
    if row is None:
        return jsonify({"error": "Post not found."}), 404
    if not community_content_authorized(row, g.current_hub_member["id"]):
        return jsonify({"error": "You cannot delete this post."}), 403
    execute("UPDATE community_posts SET is_deleted = 1, updated_at = ? WHERE id = ?", (timestamp(), post_id))
    return jsonify({"ok": True})


@app.post("/community/posts/<int:post_id>/replies")
@community_member_required
def community_create_reply_api(post_id):
    post = fetch_one("SELECT * FROM community_posts WHERE id = ? AND is_deleted = 0 AND is_hidden = 0", (post_id,))
    if post is None:
        return jsonify({"error": "Post not found."}), 404
    data = request.get_json(silent=True) or request.form
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "Write a reply before sending it."}), 400
    if len(content) > 3000:
        return jsonify({"error": "Replies must be 3,000 characters or fewer."}), 400
    parent_reply_id = data.get("parent_reply_id") or None
    if parent_reply_id:
        parent = fetch_one("SELECT id FROM community_replies WHERE id = ? AND post_id = ? AND is_deleted = 0", (parent_reply_id, post_id))
        if parent is None:
            return jsonify({"error": "That reply thread no longer exists."}), 400
    member_id = g.current_hub_member["id"]
    duplicate = fetch_one(
        "SELECT id FROM community_replies WHERE user_id = ? AND post_id = ? AND content = ? AND is_deleted = 0 AND created_at >= datetime('now', '-10 seconds') LIMIT 1",
        (member_id, post_id, content),
    )
    if duplicate:
        return jsonify({"error": "That reply was already sent."}), 409
    now = timestamp()
    cursor = execute(
        "INSERT INTO community_replies (post_id, user_id, parent_reply_id, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (post_id, member_id, parent_reply_id, content, now, now),
    )
    return jsonify({"reply": community_reply_payload(fetch_one("SELECT * FROM community_replies WHERE id = ?", (cursor.lastrowid,))) }), 201


@app.patch("/community/replies/<int:reply_id>")
@community_member_required
def community_edit_reply_api(reply_id):
    row = fetch_one("SELECT * FROM community_replies WHERE id = ? AND is_deleted = 0", (reply_id,))
    if row is None:
        return jsonify({"error": "Reply not found."}), 404
    if not community_content_authorized(row, g.current_hub_member["id"]):
        return jsonify({"error": "You cannot edit this reply."}), 403
    content = ((request.get_json(silent=True) or {}).get("content") or "").strip()
    if not content or len(content) > 3000:
        return jsonify({"error": "Reply content must be between 1 and 3,000 characters."}), 400
    execute("UPDATE community_replies SET content = ?, updated_at = ? WHERE id = ?", (content, timestamp(), reply_id))
    return jsonify({"reply": community_reply_payload(fetch_one("SELECT * FROM community_replies WHERE id = ?", (reply_id,)))})


@app.delete("/community/replies/<int:reply_id>")
@community_member_required
def community_delete_reply_api(reply_id):
    row = fetch_one("SELECT * FROM community_replies WHERE id = ? AND is_deleted = 0", (reply_id,))
    if row is None:
        return jsonify({"error": "Reply not found."}), 404
    if not community_content_authorized(row, g.current_hub_member["id"]):
        return jsonify({"error": "You cannot delete this reply."}), 403
    execute("UPDATE community_replies SET is_deleted = 1, updated_at = ? WHERE id = ?", (timestamp(), reply_id))
    return jsonify({"ok": True})


@app.post("/community/reports")
@community_member_required
def community_report_api():
    data = request.get_json(silent=True) or request.form
    post_id = data.get("post_id") or None
    reply_id = data.get("reply_id") or None
    reason = (data.get("reason") or "").strip()
    valid_reasons = {"Spam", "Harassment", "Scam", "Inappropriate content", "False information", "Other"}
    if bool(post_id) == bool(reply_id) or reason not in valid_reasons:
        return jsonify({"error": "Choose one piece of content and a valid report reason."}), 400
    if post_id and fetch_one("SELECT id FROM community_posts WHERE id = ? AND is_deleted = 0", (post_id,)) is None:
        return jsonify({"error": "Post not found."}), 404
    if reply_id and fetch_one("SELECT id FROM community_replies WHERE id = ? AND is_deleted = 0", (reply_id,)) is None:
        return jsonify({"error": "Reply not found."}), 404
    execute(
        "INSERT INTO community_reports (reporter_id, post_id, reply_id, reason, created_at) VALUES (?, ?, ?, ?, ?)",
        (g.current_hub_member["id"], post_id, reply_id, reason, timestamp()),
    )
    return jsonify({"ok": True}), 201


@app.get("/community/moderators")
@community_member_required
def community_moderators_api():
    rows = fetch_all(
        """
        SELECT hm.id, hm.full_name, cub.awarded_at, a.full_name AS awarded_by_name
        FROM community_user_badges cub
        JOIN hub_members hm ON hm.id = cub.user_id
        JOIN admins a ON a.id = cub.awarded_by
        WHERE cub.badge_type = 'moderator' AND cub.revoked_at IS NULL
        ORDER BY hm.full_name COLLATE NOCASE
        """
    )
    moderators = [dict(row) for row in rows]
    for moderator in moderators:
        moderator["initials"] = get_member_initials(moderator["full_name"])
    return jsonify({"moderators": moderators})


@app.post("/community/moderators/<int:user_id>")
@login_required
def community_award_moderator_api(user_id):
    if fetch_one("SELECT id FROM hub_members WHERE id = ? AND is_active = 1", (user_id,)) is None:
        return jsonify({"error": "Community user not found."}), 404
    existing = fetch_one("SELECT id FROM community_user_badges WHERE user_id = ? AND badge_type = 'moderator' AND revoked_at IS NULL", (user_id,))
    if existing:
        return jsonify({"error": "That user is already a moderator."}), 409
    execute(
        "INSERT INTO community_user_badges (user_id, badge_type, awarded_by, awarded_at) VALUES (?, 'moderator', ?, ?)",
        (user_id, g.current_admin["id"], timestamp()),
    )
    return jsonify({"ok": True}), 201


@app.delete("/community/moderators/<int:user_id>")
@login_required
def community_revoke_moderator_api(user_id):
    execute(
        "UPDATE community_user_badges SET revoked_at = ? WHERE user_id = ? AND badge_type = 'moderator' AND revoked_at IS NULL",
        (timestamp(), user_id),
    )
    return jsonify({"ok": True})


@app.post("/community/posts/<int:post_id>/moderate")
@community_member_required
def community_moderate_post_api(post_id):
    if not community_is_moderator(g.current_hub_member["id"]):
        return jsonify({"error": "Moderator access required."}), 403
    action = ((request.get_json(silent=True) or {}).get("action") or "").strip()
    if action not in {"hide", "unhide", "delete", "restore", "pin", "unpin"}:
        return jsonify({"error": "Unsupported moderation action."}), 400
    row = fetch_one("SELECT id FROM community_posts WHERE id = ?", (post_id,))
    if row is None:
        return jsonify({"error": "Post not found."}), 404
    field, value = {
        "hide": ("is_hidden", 1), "unhide": ("is_hidden", 0),
        "delete": ("is_deleted", 1), "restore": ("is_deleted", 0),
        "pin": ("is_pinned", 1), "unpin": ("is_pinned", 0),
    }[action]
    execute(f"UPDATE community_posts SET {field} = ?, updated_at = ? WHERE id = ?", (value, timestamp(), post_id))
    return jsonify({"ok": True})


@app.post("/community/replies/<int:reply_id>/moderate")
@community_member_required
def community_moderate_reply_api(reply_id):
    if not community_is_moderator(g.current_hub_member["id"]):
        return jsonify({"error": "Moderator access required."}), 403
    action = ((request.get_json(silent=True) or {}).get("action") or "").strip()
    if action not in {"hide", "unhide", "delete", "restore"}:
        return jsonify({"error": "Unsupported moderation action."}), 400
    row = fetch_one("SELECT id FROM community_replies WHERE id = ?", (reply_id,))
    if row is None:
        return jsonify({"error": "Reply not found."}), 404
    field, value = {
        "hide": ("is_hidden", 1), "unhide": ("is_hidden", 0),
        "delete": ("is_deleted", 1), "restore": ("is_deleted", 0),
    }[action]
    execute(f"UPDATE community_replies SET {field} = ?, updated_at = ? WHERE id = ?", (value, timestamp(), reply_id))
    return jsonify({"ok": True})


@app.route('/downloads/resources/<path:filename>')
def download_public_resource(filename):
    """Serve public resource files as attachments (force download).

    This route points at `RESOURCE_UPLOAD_DIR` and sends files with
    Content-Disposition: attachment so browsers will download instead of
    trying to render inline.
    """
    file_path = os.path.abspath(os.path.join(RESOURCE_UPLOAD_DIR, filename))
    if not file_path.startswith(os.path.abspath(RESOURCE_UPLOAD_DIR) + os.sep) or not os.path.isfile(file_path):
        abort(404)
    mimetype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return send_file(
        file_path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=os.path.basename(filename),
        conditional=True,
    )


@app.route("/hub")
def hub_index():
    if session.get("hub_member_id"):
        return redirect(url_for("hub_dashboard"))
    return redirect(url_for("hub_login"))


@app.route("/hub/login", methods=["GET", "POST"])
def hub_login():
    if session.get("hub_member_id"):
        return redirect(url_for("hub_dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        member = fetch_one("SELECT * FROM hub_members WHERE email = ? AND is_active = 1", (email,))
        valid_password = False
        if member:
            try:
                valid_password = check_password_hash(member["password_hash"], password)
            except (ValueError, TypeError):
                app.logger.warning("Invalid password hash for hub member %s", member["id"])
        if member and valid_password:
            session["hub_member_id"] = member["id"]
            flash("Welcome back to Revled Hub.", "success")
            return redirect(url_for("hub_dashboard"))
        flash("Invalid hub credentials.", "error")
    return render_template("hub_login.html")


@app.route("/hub/forgot-password", methods=["GET", "POST"])
def hub_forgot_password():
    if session.get("hub_member_id"):
        return redirect(url_for("hub_dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        token = None
        try:
            member = fetch_one("SELECT * FROM hub_members WHERE email = ? AND is_active = 1", (email,))
            if member is not None:
                token, expiry_string = create_password_reset(member)
                reset_link = build_absolute_url(url_for("hub_reset_password", token=token))
                safe_name = escape(member["full_name"])
                safe_reset_link = escape(reset_link, quote=True)
                safe_expiry = escape(expiry_string)
                plain_text = (
                    f"Hello {member['full_name']},\n\n"
                    f"We received a request to reset your Revled Vanguard Hub password.\n"
                    f"Use this secure link to choose a new password:\n{reset_link}\n\n"
                    f"This link expires on {expiry_string} UTC.\n\n"
                    f"If you did not request this reset, you can ignore this email."
                )
                html_text = (
                    f"<p>Hello {safe_name},</p>"
                    f"<p>We received a request to reset your Revled Vanguard Hub password.</p>"
                    f"<p><a href=\"{safe_reset_link}\">Reset your password</a></p>"
                    f"<p>This link expires on <strong>{safe_expiry} UTC</strong>.</p>"
                    f"<p>If you did not request this reset, you can ignore this email.</p>"
                )
                send_email_message(
                    member["email"],
                    "Reset your Revled Vanguard Hub password",
                    plain_text,
                    html_text=html_text,
                )
        except Exception:
            app.logger.exception("Failed to process hub password reset request.")
            if token:
                execute(
                    "UPDATE password_reset_tokens SET used_at = ? WHERE token = ?",
                    (timestamp(), token),
                )
            flash("We could not send the reset email right now. Please verify the mailbox password configuration and try again.", "error")
            return render_template("hub_forgot_password.html")
        flash("If that email matches an active hub account, a reset link has been sent.", "success")
        return redirect(url_for("hub_login"))
    return render_template("hub_forgot_password.html")


@app.route("/hub/reset-password/<token>", methods=["GET", "POST"])
def hub_reset_password(token):
    if session.get("hub_member_id"):
        return redirect(url_for("hub_dashboard"))
    reset_record = get_active_password_reset(token)
    if reset_record is None:
        flash("That password reset link is invalid or has expired.", "error")
        return redirect(url_for("hub_forgot_password"))
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if len(password) < 8:
            flash("Use a password with at least 8 characters.", "error")
        elif password != confirm_password:
            flash("Your passwords do not match.", "error")
        else:
            execute(
                "UPDATE hub_members SET password_hash = ?, updated_at = ? WHERE id = ?",
                (hash_password(password), timestamp(), reset_record["member_id"]),
            )
            execute(
                "UPDATE password_reset_tokens SET used_at = ? WHERE member_id = ? AND used_at IS NULL",
                (timestamp(), reset_record["member_id"]),
            )
            flash("Your password has been updated. You can sign in now.", "success")
            return redirect(url_for("hub_login"))
    return render_template("hub_reset_password.html", token=token, member_name=reset_record["full_name"])


@app.get("/hub/logout")
@hub_login_required
def hub_logout():
    session.pop("hub_member_id", None)
    flash("You have been signed out of the hub.", "success")
    return redirect(url_for("hub_login"))


@app.route("/hub/dashboard")
@hub_login_required
def hub_dashboard():
    member = g.current_hub_member
    stats = build_hub_stats(member)
    schedule_items = fetch_hub_content("schedule", member=member, limit=3)
    resource_items = fetch_hub_content("resources", member=member, limit=3)
    community_items = fetch_hub_content("community", member=member, limit=2)
    opportunity_items = fetch_hub_content("opportunities", member=member, limit=2)
    challenge_items = fetch_hub_content("challenges", member=member, limit=3)
    recent_creations = fetch_all(
        """
        SELECT *
        FROM hub_content
        WHERE is_published = 1
        ORDER BY updated_at DESC
        LIMIT 6
        """
    )
    recent_creations = [format_hub_entry(entry) for entry in recent_creations]
    recent_creations = [entry for entry in recent_creations if hub_member_can_access(member, entry)]
    return render_template(
        "hub_dashboard.html",
        member=member,
        hub_stats=stats,
        schedule_items=schedule_items,
        resource_items=resource_items,
        community_items=community_items,
        opportunity_items=opportunity_items,
        challenge_items=challenge_items,
        recent_creations=recent_creations,
        mentor_signup_url=build_absolute_url(url_for("catalyst_volunteer_mentor_page")),
        active_section="dashboard",
    )


@app.route('/hub/welcome-kit/download')
@hub_login_required
def hub_welcome_kit_download():
    kit_path = os.environ.get("WELCOME_KIT_PATH", WELCOME_KIT_PATH)
    if not kit_path or not os.path.exists(kit_path):
        abort(404)
    # Stream the welcome kit PDF as an attachment
    return send_file(kit_path, as_attachment=True, download_name=os.path.basename(kit_path), conditional=True)


def render_hub_section_page(content_type):
    member = g.current_hub_member
    config = get_hub_content_config(content_type)
    items = fetch_hub_content(content_type, member=member)
    return render_template(
        "hub_section.html",
        member=member,
        hub_stats=build_hub_stats(member),
        config=config,
        content_type=content_type,
        items=items,
        active_section=content_type,
    )


@app.route("/hub/schedule")
@hub_login_required
def hub_schedule():
    return render_hub_section_page("schedule")


@app.route("/hub/resources")
@hub_login_required
def hub_resources():
    return render_hub_section_page("resources")


@app.route("/hub/community")
@hub_login_required
def hub_community():
    return render_template(
        "community.html",
        member=g.current_hub_member,
        hub_stats=build_hub_stats(g.current_hub_member),
        active_section="community",
    )


@app.route("/hub/community/thread/<int:post_id>")
@hub_login_required
def hub_community_thread(post_id):
    member = g.current_hub_member
    post = fetch_one(
        "SELECT * FROM community_posts WHERE id = ? AND is_deleted = 0 AND is_hidden = 0",
        (post_id,),
    )
    if post is None:
        abort(404)
    return render_template(
        "community_thread.html",
        member=member,
        post=community_post_payload(post, include_replies=True),
        active_section="community",
    )


@app.route("/hub/opportunities")
@hub_login_required
def hub_opportunities():
    return render_hub_section_page("opportunities")


@app.route("/hub/challenges")
@hub_login_required
def hub_challenges():
    return render_hub_section_page("challenges")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_id"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        admin = fetch_one("SELECT * FROM admins WHERE email = ?", (email,))
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_id"] = admin["id"]
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "error")
    return render_template("admin/login.html")


@app.get("/admin/logout")
@login_required
def admin_logout():
    session.pop("admin_id", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_dashboard():
    stats = {
        "registration_total": fetch_one("SELECT COUNT(*) AS total FROM program_registrations")["total"],
        "enquiry_total": fetch_one("SELECT COUNT(*) AS total FROM enquiries")["total"],
        "contact_total": fetch_one("SELECT COUNT(*) AS total FROM contact_messages")["total"],
        "event_total": fetch_one("SELECT COUNT(*) AS total FROM events")["total"],
        "event_registration_total": fetch_one("SELECT COUNT(*) AS total FROM event_registrations")["total"],
        "seats_reserved_total": fetch_one("SELECT COALESCE(SUM(seat_count), 0) AS total FROM event_registrations")["total"],
        "resource_total": fetch_one("SELECT COUNT(*) AS total FROM resources")["total"],
        "consultation_total": fetch_one("SELECT COUNT(*) AS total FROM consultation_bookings")["total"],
        "post_total": fetch_one("SELECT COUNT(*) AS total FROM blog_posts")["total"],
        "hub_member_total": fetch_one("SELECT COUNT(*) AS total FROM hub_members")["total"],
        "hub_schedule_total": fetch_one("SELECT COUNT(*) AS total FROM hub_content WHERE content_type = 'schedule'")["total"],
        "hub_resource_total": fetch_one("SELECT COUNT(*) AS total FROM hub_content WHERE content_type = 'resources'")["total"],
        "hub_community_total": fetch_one("SELECT COUNT(*) AS total FROM hub_content WHERE content_type = 'community'")["total"],
        "hub_opportunity_total": fetch_one("SELECT COUNT(*) AS total FROM hub_content WHERE content_type = 'opportunities'")["total"],
        "hub_challenge_total": fetch_one("SELECT COUNT(*) AS total FROM hub_content WHERE content_type = 'challenges'")["total"],
        "donation_total": fetch_one("SELECT COUNT(*) AS total FROM donation_payments")["total"],
        "subscription_total": fetch_one("SELECT COUNT(*) AS total FROM membership_subscriptions")["total"],
        "failed_payment_total": (
            fetch_one("SELECT COUNT(*) AS total FROM donation_payments WHERE status = 'failed'")["total"]
            + fetch_one("SELECT COUNT(*) AS total FROM membership_subscriptions WHERE status = 'failed'")["total"]
        ),
    }
    latest_registrations = fetch_all(
        "SELECT * FROM program_registrations ORDER BY created_at DESC LIMIT 6"
    )
    latest_enquiries = fetch_all(
        "SELECT * FROM enquiries ORDER BY created_at DESC LIMIT 6"
    )
    latest_contact_messages = fetch_all(
        "SELECT * FROM contact_messages ORDER BY created_at DESC LIMIT 6"
    )
    upcoming_events = fetch_all(
        "SELECT * FROM events ORDER BY start_date ASC LIMIT 5"
    )
    latest_consultations = fetch_all(
        "SELECT * FROM consultation_bookings ORDER BY created_at DESC LIMIT 5"
    )
    latest_event_registrations = fetch_all(
        """
        SELECT er.*, e.title AS event_title
        FROM event_registrations er
        JOIN events e ON e.id = er.event_id
        ORDER BY er.created_at DESC
        LIMIT 6
        """
    )
    latest_notifications = fetch_all(
        "SELECT * FROM admin_notifications ORDER BY created_at DESC LIMIT 10"
    )
    latest_donations = fetch_all(
        "SELECT * FROM donation_payments ORDER BY created_at DESC LIMIT 6"
    )
    latest_subscriptions = fetch_all(
        "SELECT * FROM membership_subscriptions ORDER BY created_at DESC LIMIT 6"
    )
    latest_vanguard_mentor_signups = fetch_all(
        "SELECT * FROM vanguard_mentor_applications ORDER BY created_at DESC LIMIT 6"
    )
    latest_catalyst_applications = fetch_all(
        "SELECT * FROM catalyst_applications ORDER BY created_at DESC LIMIT 6"
    )
    stats["mentor_signup_total"] = fetch_one("SELECT COUNT(*) AS total FROM vanguard_mentor_applications")["total"]
    stats["catalyst_application_total"] = fetch_one("SELECT COUNT(*) AS total FROM catalyst_applications")["total"]
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        latest_registrations=latest_registrations,
        latest_enquiries=latest_enquiries,
        latest_contact_messages=latest_contact_messages,
        upcoming_events=upcoming_events,
        latest_consultations=latest_consultations,
        latest_event_registrations=latest_event_registrations,
        latest_notifications=latest_notifications,
        latest_donations=latest_donations,
        latest_subscriptions=latest_subscriptions,
        latest_vanguard_mentor_signups=latest_vanguard_mentor_signups,
        latest_catalyst_applications=latest_catalyst_applications,
    )


@app.get("/admin/community/moderators")
@login_required
def admin_community_moderators():
    search = request.args.get("q", "").strip()
    pattern = f"%{search}%"
    users = fetch_all(
        """
        SELECT hm.id, hm.full_name, hm.email, hm.is_active,
               cub.awarded_at, cub.revoked_at, a.full_name AS awarded_by_name
        FROM hub_members hm
        LEFT JOIN community_user_badges cub
          ON cub.user_id = hm.id AND cub.badge_type = 'moderator' AND cub.revoked_at IS NULL
        LEFT JOIN admins a ON a.id = cub.awarded_by
        WHERE hm.full_name LIKE ? OR hm.email LIKE ?
        ORDER BY hm.full_name COLLATE NOCASE
        LIMIT 100
        """,
        (pattern, pattern),
    )
    return render_template("admin/community_moderators.html", users=users, search=search)


@app.get("/admin/community/reports")
@login_required
def admin_community_reports():
    reports = fetch_all(
        """
        SELECT cr.*, reporter.full_name AS reporter_name,
               cp.content AS post_content, reply.content AS reply_content
        FROM community_reports cr
        JOIN hub_members reporter ON reporter.id = cr.reporter_id
        LEFT JOIN community_posts cp ON cp.id = cr.post_id
        LEFT JOIN community_replies reply ON reply.id = cr.reply_id
        ORDER BY CASE cr.status WHEN 'open' THEN 0 ELSE 1 END, cr.created_at DESC
        """
    )
    return render_template("admin/community_reports.html", reports=reports)


@app.post("/admin/community/reports/<int:report_id>/resolve")
@login_required
def admin_resolve_community_report(report_id):
    execute(
        "UPDATE community_reports SET status = 'resolved', resolved_at = ?, resolved_by = ? WHERE id = ?",
        (timestamp(), g.current_admin["id"], report_id),
    )
    flash("Community report resolved.", "success")
    return redirect(url_for("admin_community_reports"))


@app.route("/admin/vanguard-mentor-signups")
@login_required
def admin_vanguard_mentor_signups():
    signups = fetch_all("SELECT * FROM vanguard_mentor_applications ORDER BY created_at DESC")
    return render_template("admin/vanguard_mentor_signups.html", signups=signups)


@app.route("/admin/vanguard-mentor-signups/<int:mentor_id>", methods=["GET", "POST"])
@login_required
def admin_vanguard_mentor_signup_detail(mentor_id):
    signup = fetch_one("SELECT * FROM vanguard_mentor_applications WHERE id = ?", (mentor_id,))
    if signup is None:
        abort(404)
    if request.method == "POST":
        status = request.form.get("status", "new").strip() or "new"
        admin_notes = request.form.get("admin_notes", "").strip()
        execute(
            "UPDATE vanguard_mentor_applications SET status = ?, admin_notes = ?, updated_at = ? WHERE id = ?",
            (status, admin_notes, timestamp(), mentor_id),
        )
        flash("Mentor signup updated successfully.", "success")
        return redirect(url_for("admin_vanguard_mentor_signup_detail", mentor_id=mentor_id))
    return render_template("admin/vanguard_mentor_signup_detail.html", signup=signup)


@app.route("/admin/catalyst-applications")
@login_required
def admin_catalyst_applications():
    applications = fetch_all("SELECT * FROM catalyst_applications ORDER BY created_at DESC")
    return render_template("admin/catalyst_applications.html", applications=applications)


@app.route("/admin/catalyst-applications/<int:application_id>", methods=["GET", "POST"])
@login_required
def admin_catalyst_application_detail(application_id):
    application = fetch_one("SELECT * FROM catalyst_applications WHERE id = ?", (application_id,))
    if application is None:
        abort(404)
    if request.method == "POST":
        status = request.form.get("status", "new").strip() or "new"
        admin_notes = request.form.get("admin_notes", "").strip()
        execute(
            "UPDATE catalyst_applications SET status = ?, admin_notes = ?, updated_at = ? WHERE id = ?",
            (status, admin_notes, timestamp(), application_id),
        )
        flash("Catalyst application updated successfully.", "success")
        return redirect(url_for("admin_catalyst_application_detail", application_id=application_id))
    return render_template("admin/catalyst_application_detail.html", application=application)


@app.route("/admin/vanguard-milestones", methods=["GET", "POST"])
@login_required
def admin_vanguard_milestones():
    config = get_vanguard_journey_config()
    stages = config["stages"]
    form_data = {
        "activities": "\n".join(config["activities"]),
    }
    for index in range(1, 4):
        stage = stages[index - 1] if len(stages) >= index else {"label": "", "min_completed": "", "copy": "", "next_label": ""}
        form_data[f"stage_{index}_label"] = stage.get("label", "")
        form_data[f"stage_{index}_min_completed"] = stage.get("min_completed", "")
        form_data[f"stage_{index}_copy"] = stage.get("copy", "")
        form_data[f"stage_{index}_next_label"] = stage.get("next_label", "")

    if request.method == "POST":
        activities_raw = request.form.get("activities", "")
        activities = []
        for item in re.split(r"[\n,]+", activities_raw):
            slug = slugify(item)
            if slug and slug not in activities:
                activities.append(slug)

        stages = []
        stage_error = False
        for index in range(1, 4):
            label = request.form.get(f"stage_{index}_label", "").strip()
            min_completed = coerce_int(request.form.get(f"stage_{index}_min_completed", "0"), 0)
            copy = request.form.get(f"stage_{index}_copy", "").strip()
            next_label = request.form.get(f"stage_{index}_next_label", "").strip()
            if not all([label, min_completed > 0, copy, next_label]):
                flash(f"Complete every field for milestone {index}.", "error")
                stage_error = True
                break
            stages.append(
                {
                    "label": label,
                    "min_completed": min_completed,
                    "copy": copy,
                    "next_label": next_label,
                }
            )

        if not stage_error:
            if not activities:
                flash("Add at least one activity slug.", "error")
            else:
                stages.sort(key=lambda stage: stage["min_completed"])
                if any(stages[i]["min_completed"] >= stages[i + 1]["min_completed"] for i in range(len(stages) - 1)):
                    flash("Milestone thresholds must increase from one stage to the next.", "error")
                else:
                    save_vanguard_journey_config({"activities": activities, "stages": stages})
                    flash("Vanguard milestone rules updated.", "success")
                    return redirect(url_for("admin_vanguard_milestones"))

        form_data = {
            "activities": activities_raw,
        }
        for index in range(1, 4):
            form_data[f"stage_{index}_label"] = request.form.get(f"stage_{index}_label", "")
            form_data[f"stage_{index}_min_completed"] = request.form.get(f"stage_{index}_min_completed", "")
            form_data[f"stage_{index}_copy"] = request.form.get(f"stage_{index}_copy", "")
            form_data[f"stage_{index}_next_label"] = request.form.get(f"stage_{index}_next_label", "")

    return render_template("admin/vanguard_milestones.html", form_data=form_data)


@app.route("/admin/registrations")
@login_required
def admin_registrations():
    program_slug = request.args.get("program", "").strip()
    status = request.args.get("status", "").strip()
    query = "SELECT * FROM program_registrations WHERE 1=1"
    params = []
    if program_slug:
        query += " AND program_slug = ?"
        params.append(program_slug)
    if status:
        query += " AND follow_up_status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    registrations = fetch_all(query, tuple(params))
    return render_template(
        "admin/registrations.html",
        registrations=registrations,
        current_program=program_slug,
        current_status=status,
        statuses=["new", "contacted", "in-progress", "completed"],
    )


@app.route("/admin/registrations/<int:registration_id>", methods=["GET", "POST"])
@login_required
def admin_registration_detail(registration_id):
    registration = fetch_one("SELECT * FROM program_registrations WHERE id = ?", (registration_id,))
    if registration is None:
        abort(404)
    if request.method == "POST":
        follow_up_status = request.form.get("follow_up_status", "new").strip() or "new"
        follow_up_notes = request.form.get("follow_up_notes", "").strip()
        admin_notes = request.form.get("admin_notes", "").strip()
        execute(
            """
            UPDATE program_registrations
            SET follow_up_status = ?, follow_up_notes = ?, admin_notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (follow_up_status, follow_up_notes, admin_notes, timestamp(), registration_id),
        )
        flash("Registration follow-up details updated.", "success")
        return redirect(url_for("admin_registration_detail", registration_id=registration_id))
    return render_template("admin/registration_detail.html", registration=registration)


@app.route("/admin/enquiries")
@login_required
def admin_enquiries():
    enquiry_type = request.args.get("type", "").strip()
    status = request.args.get("status", "").strip()
    query = "SELECT * FROM enquiries WHERE 1=1"
    params = []
    if enquiry_type:
        query += " AND enquiry_type = ?"
        params.append(enquiry_type)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    enquiries = fetch_all(query, tuple(params))
    return render_template("admin/enquiries.html", enquiries=enquiries, current_type=enquiry_type, current_status=status)


@app.route("/admin/enquiries/<int:enquiry_id>", methods=["GET", "POST"])
@login_required
def admin_enquiry_detail(enquiry_id):
    enquiry = fetch_one("SELECT * FROM enquiries WHERE id = ?", (enquiry_id,))
    if enquiry is None:
        abort(404)
    if request.method == "POST":
        status = request.form.get("status", "new").strip() or "new"
        admin_notes = request.form.get("admin_notes", "").strip()
        execute(
            "UPDATE enquiries SET status = ?, admin_notes = ?, updated_at = ? WHERE id = ?",
            (status, admin_notes, timestamp(), enquiry_id),
        )
        flash("Enquiry updated successfully.", "success")
        return redirect(url_for("admin_enquiry_detail", enquiry_id=enquiry_id))
    return render_template("admin/enquiry_detail.html", enquiry=enquiry)


@app.route("/admin/consultations")
@login_required
def admin_consultations():
    consultations = fetch_all("SELECT * FROM consultation_bookings ORDER BY created_at DESC")
    return render_template("admin/consultations.html", consultations=consultations)


@app.route("/admin/contact-messages")
@login_required
def admin_contact_messages():
    status = request.args.get("status", "").strip()
    query = "SELECT * FROM contact_messages WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    messages = fetch_all(query, tuple(params))
    return render_template("admin/contact_messages.html", messages=messages, current_status=status)


@app.route("/admin/contact-messages/<int:message_id>", methods=["GET", "POST"])
@login_required
def admin_contact_message_detail(message_id):
    message = fetch_one("SELECT * FROM contact_messages WHERE id = ?", (message_id,))
    if message is None:
        abort(404)
    if request.method == "POST":
        status = request.form.get("status", "new").strip() or "new"
        admin_notes = request.form.get("admin_notes", "").strip()
        execute(
            "UPDATE contact_messages SET status = ?, admin_notes = ?, updated_at = ? WHERE id = ?",
            (status, admin_notes, timestamp(), message_id),
        )
        flash("Contact message updated successfully.", "success")
        return redirect(url_for("admin_contact_message_detail", message_id=message_id))
    return render_template("admin/contact_message_detail.html", message=message)


@app.route("/admin/notifications")
@login_required
def admin_notifications():
    notifications = fetch_all("SELECT * FROM admin_notifications ORDER BY created_at DESC LIMIT 200")
    execute("UPDATE admin_notifications SET is_read = 1 WHERE is_read = 0")
    return render_template("admin/notifications.html", notifications=notifications)


@app.route("/admin/consultations/<int:booking_id>", methods=["GET", "POST"])
@login_required
def admin_consultation_detail(booking_id):
    booking = fetch_one("SELECT * FROM consultation_bookings WHERE id = ?", (booking_id,))
    if booking is None:
        abort(404)
    if request.method == "POST":
        status = request.form.get("status", "new").strip() or "new"
        admin_notes = request.form.get("admin_notes", "").strip()
        execute(
            "UPDATE consultation_bookings SET status = ?, admin_notes = ?, updated_at = ? WHERE id = ?",
            (status, admin_notes, timestamp(), booking_id),
        )
        flash("Consultation booking updated successfully.", "success")
        return redirect(url_for("admin_consultation_detail", booking_id=booking_id))
    return render_template("admin/consultation_detail.html", booking=booking)


@app.route("/admin/events")
@login_required
def admin_events():
    events = fetch_all(
        """
        SELECT e.*, COUNT(er.id) AS registration_count, COALESCE(SUM(er.seat_count), 0) AS seats_reserved
        FROM events e
        LEFT JOIN event_registrations er ON er.event_id = e.id
        GROUP BY e.id
        ORDER BY e.start_date ASC
        """
    )
    return render_template("admin/events_list.html", events=events)


@app.route("/admin/events/new", methods=["GET", "POST"])
@login_required
def admin_event_new():
    form_data = {
        "title": "",
        "slug": "",
        "summary": "",
        "description": "",
        "location": "",
        "event_type": "bootcamp",
        "program_slug": "",
        "start_date": "",
        "end_date": "",
        "booking_link": "",
        "registration_label": "",
        "seat_limit": "0",
        "requires_registration": "1",
        "is_published": "1",
    }
    if request.method == "POST":
        form_data = {key: request.form.get(key, "").strip() for key in form_data}
        slug = form_data["slug"] or slugify(form_data["title"])
        existing = fetch_one("SELECT id FROM events WHERE slug = ?", (slug,))
        required = ["title", "summary", "description", "location", "start_date"]
        if any(not form_data[field] for field in required):
            flash("Please complete the required event fields.", "error")
        elif existing is not None:
            flash("That event slug already exists.", "error")
        else:
            now = timestamp()
            execute(
                """
                INSERT INTO events (
                    title, slug, summary, description, location, event_type, program_slug, start_date, end_date,
                    booking_link, registration_label, seat_limit, requires_registration, is_published, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    form_data["title"],
                    slug,
                    form_data["summary"],
                    form_data["description"],
                    form_data["location"],
                    form_data["event_type"],
                    form_data["program_slug"] or None,
                    form_data["start_date"],
                    form_data["end_date"] or None,
                    form_data["booking_link"],
                    form_data["registration_label"] or "Register",
                    max(0, coerce_int(form_data["seat_limit"], 0)),
                    1 if form_data["requires_registration"] == "1" else 0,
                    1 if form_data["is_published"] == "1" else 0,
                    now,
                    now,
                ),
            )
            flash("Event created successfully.", "success")
            return redirect(url_for("admin_events"))
    return render_template("admin/event_form.html", form_data=form_data, event=None)


@app.route("/admin/events/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
def admin_event_edit(event_id):
    event = fetch_one("SELECT * FROM events WHERE id = ?", (event_id,))
    if event is None:
        abort(404)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        slug = request.form.get("slug", "").strip() or slugify(title)
        summary = request.form.get("summary", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()
        event_type = request.form.get("event_type", "bootcamp").strip()
        program_slug = request.form.get("program_slug", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        booking_link = request.form.get("booking_link", "").strip()
        registration_label = request.form.get("registration_label", "").strip() or "Register"
        seat_limit = max(0, coerce_int(request.form.get("seat_limit", "0"), 0))
        requires_registration = 1 if request.form.get("requires_registration", "0").strip() == "1" else 0
        is_published = 1 if request.form.get("is_published", "0").strip() == "1" else 0
        existing = fetch_one("SELECT id FROM events WHERE slug = ? AND id != ?", (slug, event_id))
        if not all([title, summary, description, location, start_date]):
            flash("Please complete the required event fields.", "error")
        elif existing is not None:
            flash("That event slug already exists.", "error")
        else:
            execute(
                """
                UPDATE events
                SET title = ?, slug = ?, summary = ?, description = ?, location = ?, event_type = ?, program_slug = ?,
                    start_date = ?, end_date = ?, booking_link = ?, registration_label = ?, seat_limit = ?, requires_registration = ?,
                    is_published = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    title,
                    slug,
                    summary,
                    description,
                    location,
                    event_type,
                    program_slug or None,
                    start_date,
                    end_date or None,
                    booking_link,
                    registration_label,
                    seat_limit,
                    requires_registration,
                    is_published,
                    timestamp(),
                    event_id,
                ),
            )
            flash("Event updated successfully.", "success")
            return redirect(url_for("admin_event_edit", event_id=event_id))
    registrations = fetch_all("SELECT * FROM event_registrations WHERE event_id = ? ORDER BY created_at DESC", (event_id,))
    return render_template("admin/event_form.html", form_data=event, event=event, registrations=registrations)


@app.post("/admin/events/<int:event_id>/delete")
@login_required
def admin_event_delete(event_id):
    execute("DELETE FROM events WHERE id = ?", (event_id,))
    flash("Event deleted.", "success")
    return redirect(url_for("admin_events"))


@app.route("/admin/events/<int:event_id>/registrations")
@login_required
def admin_event_registrations(event_id):
    event = fetch_one("SELECT * FROM events WHERE id = ?", (event_id,))
    if event is None:
        abort(404)
    registrations = fetch_all("SELECT * FROM event_registrations WHERE event_id = ? ORDER BY created_at DESC", (event_id,))
    reserved_total = fetch_one("SELECT COALESCE(SUM(seat_count), 0) AS total FROM event_registrations WHERE event_id = ?", (event_id,))["total"]
    return render_template("admin/event_registrations.html", event=event, registrations=registrations, reserved_total=reserved_total)


@app.route("/admin/resources")
@login_required
def admin_resources():
    resources = fetch_all("SELECT * FROM resources ORDER BY created_at DESC")
    return render_template("admin/resources_list.html", resources=resources)


@app.route("/admin/resources/new", methods=["GET", "POST"])
@login_required
def admin_resource_new():
    form_data = {
        "title": "",
        "slug": "",
        "resource_type": "guide",
        "audience": "all",
        "summary": "",
        "description": "",
        "price_naira": "0",
        "external_url": "",
        "cta_label": "",
        "is_published": "1",
    }
    if request.method == "POST":
        form_data = {key: request.form.get(key, "").strip() for key in form_data}
        slug = form_data["slug"] or slugify(form_data["title"])
        existing = fetch_one("SELECT id FROM resources WHERE slug = ?", (slug,))
        uploaded_file = save_resource_file(request.files.get("uploaded_file"))
        required = ["title", "summary", "description"]
        if any(not form_data[field] for field in required):
            flash("Please complete the required resource fields.", "error")
        elif existing is not None:
            flash("That resource slug already exists.", "error")
        elif request.files.get("uploaded_file") and request.files["uploaded_file"].filename and not uploaded_file:
            flash("That file type is not supported for upload.", "error")
        else:
            now = timestamp()
            execute(
                """
                INSERT INTO resources (
                    title, slug, resource_type, audience, summary, description, price_naira, external_url,
                    cta_label, uploaded_file, is_published, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    form_data["title"],
                    slug,
                    form_data["resource_type"],
                    form_data["audience"],
                    form_data["summary"],
                    form_data["description"],
                    int(form_data["price_naira"] or 0),
                    form_data["external_url"],
                    form_data["cta_label"] or "Access Resource",
                    uploaded_file or "",
                    1 if form_data["is_published"] == "1" else 0,
                    now,
                    now,
                ),
            )
            flash("Resource created successfully.", "success")
            return redirect(url_for("admin_resources"))
    return render_template("admin/resource_form.html", form_data=form_data, resource=None)


@app.route("/admin/resources/<int:resource_id>/edit", methods=["GET", "POST"])
@login_required
def admin_resource_edit(resource_id):
    resource = fetch_one("SELECT * FROM resources WHERE id = ?", (resource_id,))
    if resource is None:
        abort(404)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        slug = request.form.get("slug", "").strip() or slugify(title)
        resource_type = request.form.get("resource_type", "guide").strip()
        audience = request.form.get("audience", "all").strip()
        summary = request.form.get("summary", "").strip()
        description = request.form.get("description", "").strip()
        price_naira = int(request.form.get("price_naira", "0").strip() or 0)
        external_url = request.form.get("external_url", "").strip()
        cta_label = request.form.get("cta_label", "").strip() or "Access Resource"
        is_published = 1 if request.form.get("is_published", "0").strip() == "1" else 0
        existing = fetch_one("SELECT id FROM resources WHERE slug = ? AND id != ?", (slug, resource_id))
        uploaded_file = save_resource_file(request.files.get("uploaded_file"))
        if not all([title, summary, description]):
            flash("Please complete the required resource fields.", "error")
        elif existing is not None:
            flash("That resource slug already exists.", "error")
        elif request.files.get("uploaded_file") and request.files["uploaded_file"].filename and not uploaded_file:
            flash("That file type is not supported for upload.", "error")
        else:
            stored_file = uploaded_file or resource["uploaded_file"]
            execute(
                """
                UPDATE resources
                SET title = ?, slug = ?, resource_type = ?, audience = ?, summary = ?, description = ?,
                    price_naira = ?, external_url = ?, cta_label = ?, uploaded_file = ?, is_published = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    title,
                    slug,
                    resource_type,
                    audience,
                    summary,
                    description,
                    price_naira,
                    external_url,
                    cta_label,
                    stored_file,
                    is_published,
                    timestamp(),
                    resource_id,
                ),
            )
            flash("Resource updated successfully.", "success")
            return redirect(url_for("admin_resource_edit", resource_id=resource_id))
    return render_template("admin/resource_form.html", form_data=resource, resource=resource)


@app.post("/admin/resources/<int:resource_id>/delete")
@login_required
def admin_resource_delete(resource_id):
    execute("DELETE FROM resources WHERE id = ?", (resource_id,))
    flash("Resource deleted.", "success")
    return redirect(url_for("admin_resources"))


@app.route("/admin/hub/members")
@login_required
def admin_hub_members():
    # Optional filter by user_type (ENTREPRENEUR / PROFESSIONAL)
    user_type = request.args.get('user_type', '').strip()
    if user_type:
        members = fetch_all("SELECT * FROM hub_members WHERE user_type = ? ORDER BY created_at DESC", (user_type,))
    else:
        members = fetch_all("SELECT * FROM hub_members ORDER BY created_at DESC")
    return render_template(
        "admin/hub_members_list.html",
        members=[format_hub_member(member) for member in members],
        hub_user_types=HUB_USER_TYPES,
        selected_user_type=user_type,
    )


@app.route("/admin/hub/members/new", methods=["GET", "POST"])
@login_required
def admin_hub_member_new():
    form_data = {
        "full_name": "",
        "email": "",
        "password": "",
        "user_type": "ENTREPRENEUR",
        "industry_track": "General",
        "membership_tier": "ESSENTIAL",
        "progress_percentage": "0",
        "bio": "",
        "is_active": "1",
    }
    if request.method == "POST":
        form_data = {key: request.form.get(key, "").strip() for key in form_data}
        existing = fetch_one("SELECT id FROM hub_members WHERE email = ?", (form_data["email"].lower(),))
        if not all([form_data["full_name"], form_data["email"], form_data["password"]]):
            flash("Full name, email, and password are required for hub members.", "error")
        elif existing is not None:
            flash("A hub member with that email already exists.", "error")
        else:
            now = timestamp()
            execute(
                """
                INSERT INTO hub_members (
                    full_name, email, password_hash, user_type, industry_track, membership_tier, progress_percentage,
                    bio, is_active, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    form_data["full_name"],
                    form_data["email"].lower(),
                    hash_password(form_data["password"]),
                    normalize_user_type(form_data["user_type"]),
                    form_data["industry_track"] or "General",
                    form_data["membership_tier"] or "ESSENTIAL",
                    max(0, min(100, coerce_int(form_data["progress_percentage"], 0))),
                    form_data["bio"],
                    1 if form_data["is_active"] == "1" else 0,
                    now,
                    now,
                ),
            )
            flash("Hub member account created successfully.", "success")
            return redirect(url_for("admin_hub_members"))
    return render_template("admin/hub_member_form.html", form_data=form_data, member=None)


@app.route("/admin/hub/members/<int:member_id>/edit", methods=["GET", "POST"])
@login_required
def admin_hub_member_edit(member_id):
    member = fetch_one("SELECT * FROM hub_members WHERE id = ?", (member_id,))
    if member is None:
        abort(404)
    form_data = dict(member)
    form_data["password"] = ""
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        user_type = normalize_user_type(request.form.get("user_type", "ENTREPRENEUR"))
        industry_track = request.form.get("industry_track", "").strip() or "General"
        membership_tier = request.form.get("membership_tier", "ESSENTIAL").strip() or "ESSENTIAL"
        progress_percentage = max(0, min(100, coerce_int(request.form.get("progress_percentage", "0"), 0)))
        bio = request.form.get("bio", "").strip()
        is_active = 1 if request.form.get("is_active", "0").strip() == "1" else 0
        existing = fetch_one("SELECT id FROM hub_members WHERE email = ? AND id != ?", (email, member_id))
        if not all([full_name, email]):
            flash("Full name and email are required.", "error")
        elif existing is not None:
            flash("Another hub member already uses that email.", "error")
        else:
            password_hash = hash_password(password) if password else member["password_hash"]
            execute(
                """
                UPDATE hub_members
                SET full_name = ?, email = ?, password_hash = ?, user_type = ?, industry_track = ?, membership_tier = ?,
                    progress_percentage = ?, bio = ?, is_active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    full_name,
                    email,
                    password_hash,
                    user_type,
                    industry_track,
                    membership_tier,
                    progress_percentage,
                    bio,
                    is_active,
                    timestamp(),
                    member_id,
                ),
            )
            flash("Hub member updated successfully.", "success")
            return redirect(url_for("admin_hub_member_edit", member_id=member_id))
        form_data = {
            "full_name": full_name,
            "email": email,
            "password": password,
            "user_type": user_type,
            "industry_track": industry_track,
            "membership_tier": membership_tier,
            "progress_percentage": str(progress_percentage),
            "bio": bio,
            "is_active": str(is_active),
        }
    return render_template("admin/hub_member_form.html", form_data=form_data, member=format_hub_member(member))


@app.post("/admin/hub/members/<int:member_id>/delete")
@login_required
def admin_hub_member_delete(member_id):
    execute("DELETE FROM hub_members WHERE id = ?", (member_id,))
    flash("Hub member deleted.", "success")
    return redirect(url_for("admin_hub_members"))


def get_hub_content_form_data(content_type, source=None):
    config = get_hub_content_config(content_type)
    form_data = {
        "title": "",
        "slug": "",
        "summary": "",
        "description": "",
        "meta_one": "",
        "meta_two": "",
        "starts_at": "",
        "ends_at": "",
        "location": "",
        "status_text": "",
        "badge_text": "",
        "cta_label": config["default_cta"],
        "cta_url": "",
        "audience_user_types": "ALL",
        "access_tier": "ALL",
        "sort_order": "0",
        "is_published": "1",
        "uploaded_file": "",
        "uploaded_file_name": "",
    }
    if source:
        form_data.update({key: source[key] for key in form_data if key in source.keys()})
        form_data["is_published"] = str(source["is_published"])
        form_data["sort_order"] = str(source["sort_order"])
    form_data["selected_user_types"] = parse_target_user_types(form_data.get("audience_user_types"))
    return form_data


@app.route("/admin/hub/content/<content_type>")
@login_required
def admin_hub_content_list(content_type):
    config = get_hub_content_config(content_type)
    items = [
        format_hub_entry(item) for item in fetch_all(
        """
        SELECT *
        FROM hub_content
        WHERE content_type = ?
        ORDER BY sort_order ASC, created_at DESC
        """,
        (content_type,),
        )
    ]
    return render_template("admin/hub_content_list.html", config=config, content_type=content_type, items=items)


@app.route("/admin/hub/content/<content_type>/new", methods=["GET", "POST"])
@login_required
def admin_hub_content_new(content_type):
    config = get_hub_content_config(content_type)
    form_data = get_hub_content_form_data(content_type)
    if request.method == "POST":
        form_data = {key: request.form.get(key, "").strip() for key in form_data}
        selected_user_types = normalize_target_user_types(request.form.getlist("user_types"))
        uploaded_info = save_hub_file(request.files.get("uploaded_file"))
        slug = form_data["slug"] or slugify(form_data["title"])
        existing = fetch_one("SELECT id FROM hub_content WHERE slug = ?", (slug,))
        if not all([form_data["title"], form_data["summary"], form_data["description"]]):
            flash(f"Please complete the required {config['singular']} fields.", "error")
        elif existing is not None:
            flash("That hub content slug already exists.", "error")
        elif request.files.get("uploaded_file") and request.files["uploaded_file"].filename and not uploaded_info:
            flash("That uploaded hub file type is not supported.", "error")
        else:
            now = timestamp()
            execute(
                """
                INSERT INTO hub_content (
                    content_type, slug, title, summary, description, meta_one, meta_two, starts_at, ends_at, location,
                    status_text, badge_text, cta_label, cta_url, audience_user_types, uploaded_file, uploaded_file_name,
                    access_tier, sort_order, is_published, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    content_type,
                    slug,
                    form_data["title"],
                    form_data["summary"],
                    form_data["description"],
                    form_data["meta_one"],
                    form_data["meta_two"],
                    form_data["starts_at"] or None,
                    form_data["ends_at"] or None,
                    form_data["location"],
                    form_data["status_text"],
                    form_data["badge_text"],
                    form_data["cta_label"] or config["default_cta"],
                    form_data["cta_url"],
                    serialize_target_user_types(selected_user_types),
                    uploaded_info["stored_name"] if uploaded_info else "",
                    uploaded_info["original_name"] if uploaded_info else "",
                    form_data["access_tier"] or "ALL",
                    coerce_int(form_data["sort_order"], 0),
                    1 if form_data["is_published"] == "1" else 0,
                    now,
                    now,
                ),
            )
            flash(f"{config['label']} item created successfully.", "success")
            return redirect(url_for("admin_hub_content_list", content_type=content_type))
        form_data["selected_user_types"] = selected_user_types
    return render_template("admin/hub_content_form.html", config=config, content_type=content_type, form_data=form_data, item=None)


@app.route("/admin/hub/content/<content_type>/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def admin_hub_content_edit(content_type, item_id):
    config = get_hub_content_config(content_type)
    item = fetch_one("SELECT * FROM hub_content WHERE id = ? AND content_type = ?", (item_id, content_type))
    if item is None:
        abort(404)
    form_data = get_hub_content_form_data(content_type, item)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        slug = request.form.get("slug", "").strip() or slugify(title)
        summary = request.form.get("summary", "").strip()
        description = request.form.get("description", "").strip()
        meta_one = request.form.get("meta_one", "").strip()
        meta_two = request.form.get("meta_two", "").strip()
        starts_at = request.form.get("starts_at", "").strip()
        ends_at = request.form.get("ends_at", "").strip()
        location = request.form.get("location", "").strip()
        status_text = request.form.get("status_text", "").strip()
        badge_text = request.form.get("badge_text", "").strip()
        cta_label = request.form.get("cta_label", "").strip() or config["default_cta"]
        cta_url = request.form.get("cta_url", "").strip()
        selected_user_types = normalize_target_user_types(request.form.getlist("user_types"))
        access_tier = request.form.get("access_tier", "ALL").strip() or "ALL"
        sort_order = coerce_int(request.form.get("sort_order", "0"), 0)
        is_published = 1 if request.form.get("is_published", "0").strip() == "1" else 0
        existing = fetch_one("SELECT id FROM hub_content WHERE slug = ? AND id != ?", (slug, item_id))
        uploaded_info = save_hub_file(request.files.get("uploaded_file"))
        if not all([title, summary, description]):
            flash(f"Please complete the required {config['singular']} fields.", "error")
        elif existing is not None:
            flash("That hub content slug already exists.", "error")
        elif request.files.get("uploaded_file") and request.files["uploaded_file"].filename and not uploaded_info:
            flash("That uploaded hub file type is not supported.", "error")
        else:
            stored_file = uploaded_info["stored_name"] if uploaded_info else (item["uploaded_file"] or "")
            original_file_name = uploaded_info["original_name"] if uploaded_info else (item["uploaded_file_name"] or "")
            execute(
                """
                UPDATE hub_content
                SET slug = ?, title = ?, summary = ?, description = ?, meta_one = ?, meta_two = ?, starts_at = ?, ends_at = ?,
                    location = ?, status_text = ?, badge_text = ?, cta_label = ?, cta_url = ?, audience_user_types = ?,
                    uploaded_file = ?, uploaded_file_name = ?, access_tier = ?, sort_order = ?,
                    is_published = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    slug,
                    title,
                    summary,
                    description,
                    meta_one,
                    meta_two,
                    starts_at or None,
                    ends_at or None,
                    location,
                    status_text,
                    badge_text,
                    cta_label,
                    cta_url,
                    serialize_target_user_types(selected_user_types),
                    stored_file,
                    original_file_name,
                    access_tier,
                    sort_order,
                    is_published,
                    timestamp(),
                    item_id,
                ),
            )
            flash(f"{config['label']} item updated successfully.", "success")
            return redirect(url_for("admin_hub_content_edit", content_type=content_type, item_id=item_id))
        form_data = {
            "title": title,
            "slug": slug,
            "summary": summary,
            "description": description,
            "meta_one": meta_one,
            "meta_two": meta_two,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "location": location,
            "status_text": status_text,
            "badge_text": badge_text,
            "cta_label": cta_label,
            "cta_url": cta_url,
            "audience_user_types": serialize_target_user_types(selected_user_types),
            "selected_user_types": selected_user_types,
            "access_tier": access_tier,
            "sort_order": str(sort_order),
            "is_published": str(is_published),
            "uploaded_file": uploaded_info["stored_name"] if uploaded_info else (item["uploaded_file"] or ""),
            "uploaded_file_name": uploaded_info["original_name"] if uploaded_info else (item["uploaded_file_name"] or ""),
        }
    return render_template("admin/hub_content_form.html", config=config, content_type=content_type, form_data=form_data, item=item)


@app.post("/admin/hub/content/<content_type>/<int:item_id>/delete")
@login_required
def admin_hub_content_delete(content_type, item_id):
    get_hub_content_config(content_type)
    execute("DELETE FROM hub_content WHERE id = ? AND content_type = ?", (item_id, content_type))
    flash("Hub content deleted.", "success")
    return redirect(url_for("admin_hub_content_list", content_type=content_type))


@app.route("/admin/blog")
@login_required
def admin_blog():
    posts = fetch_all(
        """
        SELECT bp.*, COUNT(DISTINCT bc.id) AS comment_count, COUNT(DISTINCT bl.id) AS like_count
        FROM blog_posts bp
        LEFT JOIN blog_comments bc ON bc.post_id = bp.id
        LEFT JOIN blog_likes bl ON bl.post_id = bp.id
        GROUP BY bp.id
        ORDER BY bp.updated_at DESC
        """
    )
    return render_template("admin/blog_list.html", posts=posts)


@app.route("/admin/blog/new", methods=["GET", "POST"])
@login_required
def admin_blog_new():
    form_data = {
        "title": "",
        "slug": "",
        "excerpt": "",
        "content": "",
        "image_url": "",
        "is_published": "1"
    }

    if request.method == "POST":
        def safe_str(value):
            return (value or "").encode("utf-8", "ignore").decode("utf-8").strip()

        form_data = {k: safe_str(request.form.get(k)) for k in form_data}

        title = form_data["title"]
        excerpt = form_data["excerpt"]
        content = form_data["content"]

        # slug fallback
        slug = form_data["slug"] or slugify(title)

        # check existing slug
        existing = fetch_one(
            "SELECT id FROM blog_posts WHERE slug = ?",
            (slug,)
        )

        uploaded_image_url = save_public_image_file(
            request.files.get("image_upload"),
            BLOG_UPLOAD_DIR,
            url_for("static", filename="uploads/blog"),
        )

        # validation
        if not title or not excerpt or not content:
            flash("Title, excerpt, and content are required.", "error")

        elif existing:
            flash("That blog slug already exists. Please choose another one.", "error")

        elif request.files.get("image_upload") and request.files["image_upload"].filename and not uploaded_image_url:
            flash("That blog image file type is not supported.", "error")

        else:
            now = timestamp()
            is_published = 1 if form_data["is_published"] == "1" else 0
            published_at = now if is_published else None

            execute(
                """
                INSERT INTO blog_posts
                (title, slug, excerpt, content, image_url,
                 is_published, published_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    slug,
                    excerpt,
                    content,  # HTML safe from Quill
                    uploaded_image_url or form_data["image_url"],
                    is_published,
                    published_at,
                    now,
                    now,
                ),
            )

            flash("Blog post created successfully.", "success")
            return redirect(url_for("admin_blog"))

        if uploaded_image_url:
            form_data["image_url"] = uploaded_image_url

    return render_template("admin/blog_form.html", form_data=form_data, post=None)
    
@app.route("/admin/blog/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
def admin_blog_edit(post_id):
    post = fetch_one("SELECT * FROM blog_posts WHERE id = ?", (post_id,))
    if post is None:
        abort(404)
    
    if request.method == "POST":
        def safe_str(value):
            return (value or "").encode("utf-8", "ignore").decode("utf-8").strip()
        
        title = safe_str(request.form.get("title"))
        slug = safe_str(request.form.get("slug")) or slugify(title)
        excerpt = safe_str(request.form.get("excerpt"))
        content = safe_str(request.form.get("content"))
        image_url = safe_str(request.form.get("image_url"))
        
        uploaded_image_url = save_public_image_file(
            request.files.get("image_upload"),
            BLOG_UPLOAD_DIR,
            url_for("static", filename="uploads/blog"),
        )
        
        is_published = 1 if request.form.get("is_published", "0") == "1" else 0
        
        existing = fetch_one(
            "SELECT id FROM blog_posts WHERE slug = ? AND id != ?",
            (slug, post_id)
        )
        
        if not title or not excerpt or not content:
            flash("Title, excerpt, and content are required.", "error")
        elif existing:
            flash("That blog slug already exists. Please choose another one.", "error")
        elif request.files.get("image_upload") and request.files["image_upload"].filename and not uploaded_image_url:
            flash("That blog image file type is not supported.", "error")
        else:
            published_at = (post["published_at"] or timestamp()) if is_published else None
            
            execute(
                """
                UPDATE blog_posts
                SET title = ?, slug = ?, excerpt = ?, content = ?,
                    image_url = ?, is_published = ?, published_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    title,
                    slug,
                    excerpt,
                    content,
                    uploaded_image_url or image_url,
                    is_published,
                    published_at,
                    timestamp(),
                    post_id,
                ),
            )
            
            flash("Blog post updated successfully.", "success")
            return redirect(url_for("admin_blog_edit", post_id=post_id))
    
    comments = fetch_all(
        "SELECT * FROM blog_comments WHERE post_id = ? ORDER BY created_at DESC",
        (post_id,)
    )
    
    return render_template(
        "admin/blog_form.html",
        form_data=post,
        post=post,
        comments=comments
    )
@app.post("/admin/blog/<int:post_id>/delete")
@login_required
def admin_blog_delete(post_id):
    execute("DELETE FROM blog_posts WHERE id = ?", (post_id,))
    flash("Blog post deleted.", "success")
    return redirect(url_for("admin_blog"))


@app.post("/admin/comments/<int:comment_id>/delete")
@login_required
def admin_comment_delete(comment_id):
    comment = fetch_one("SELECT post_id FROM blog_comments WHERE id = ?", (comment_id,))
    if comment is None:
        abort(404)
    execute("DELETE FROM blog_comments WHERE id = ?", (comment_id,))
    flash("Comment deleted.", "success")
    return redirect(url_for("admin_blog_edit", post_id=comment["post_id"]))


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("500.html"), 500


init_db()
with app.app_context():
    seed_runtime_config()
    refresh_runtime_config()


if __name__ == "__main__":
    app.run(debug=True, port=5050)
