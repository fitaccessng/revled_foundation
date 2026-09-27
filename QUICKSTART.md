# 🚀 Revled Foundation Website - Quick Start Guide

## ⚡ One-Minute Setup

### 1. Install Python Dependencies
```bash
cd /Users/macbookpro/Documents/revled.org
pip install -r requirements.txt
```

### 2. Run the Server
```bash
python app.py
```

### 3. Open in Browser
```
http://localhost:5000
```

**That's it!** Your Revled website is now live. 🎉

---

## 📋 What You Got

### ✅ Complete Website with 7 Pages
- **Homepage** - Hero, journey visual, impact stats, testimonials
- **About** - Story, vision, values, Revled model (0-25)
- **Programs** - All 4 program stages with full details
- **Impact** - Metrics, stories, community reach
- **Get Involved** - Partnerships, sponsorship tiers, volunteering
- **Resources** - Learning materials, guides, videos
- **Contact** - Form, FAQ, location info

### ✅ Production-Ready Features
- ✨ Smooth animations & transitions
- 📱 Fully responsive design
- 🎨 Custom color system (Blue, Orange, Cream)
- 💬 Contact form with validation
- 🔍 SEO-friendly structure
- ♿ Accessibility compliant
- ⚡ Performance optimized

### ✅ Backend Functionality
- Form submission handling
- Flash message notifications
- Error pages (404, 500)
- Dynamic routing
- Jinja2 templating

---

## 🎨 Customization Guide

### Change Colors
Edit `/templates/base.html` (lines 15-19):
```css
--deep-blue: #003f87;      /* Primary blue */
--warm-orange: #ff6b35;    /* Accent orange */
--soft-cream: #faf8f3;     /* Background cream */
```

### Update Organization Info
Search and replace in templates:
- Organization name: "Revled Foundation"
- Contact email: "hello@revled.org"
- Phone: "+234 701 234 5678"
- Address: "Lagos, Nigeria"

### Add Real Images
Replace placeholder emoji boxes with actual images:
```html
<!-- Instead of: <span class="text-8xl">🌱</span> -->
<img src="{{ url_for('static', filename='images/roots.jpg') }}" alt="Revled Roots">
```

### Enable Email Notifications
Update the contact route in `app.py` to send emails (requires Flask-Mail):
```bash
pip install Flask-Mail
```

---

## 📚 File Structure Breakdown

```
revled.org/
├── app.py                      # Flask app (all routes here)
├── requirements.txt            # Dependencies
├── README.md                   # Full documentation
├── QUICKSTART.md              # This file
├── .gitignore                 # Git configuration
│
├── templates/                 # All HTML pages
│   ├── base.html             # Master template (navbar, footer, styles)
│   ├── home.html             # Homepage
│   ├── about.html            # About page
│   ├── programs.html         # Programs showcase
│   ├── impact.html           # Impact metrics
│   ├── get-involved.html     # Partnerships
│   ├── resources.html        # Learning materials
│   ├── contact.html          # Contact form
│   ├── 404.html              # Not found
│   ├── 500.html              # Server error
│   └── components/
│       ├── navbar.html       # Navigation
│       └── footer.html       # Footer
│
└── static/                   # Static assets
    ├── css/
    │   └── style.css        # Custom styles
    └── js/
        └── animations.js    # Scroll & hover effects
```

---

## 🔧 Common Tasks

### Add a New Page
1. Create `templates/new-page.html` extending `base.html`:
```html
{% extends "base.html" %}
{% block content %}
<!-- Your content here -->
{% endblock %}
```

2. Add route in `app.py`:
```python
@app.route('/new-page')
def new_page():
    return render_template('new-page.html')
```

3. Add link in navbar (`templates/components/navbar.html`):
```html
<a href="{{ url_for('new_page') }}">New Page</a>
```

### Update Program Information
Edit the relevant sections in `/templates/programs.html`.

### Change Homepage Hero Text
Edit `/templates/home.html` around lines 10-30.

### Modify Impact Numbers
Update the `data-target` values in `/templates/impact.html` and `/templates/home.html`.

---

## 🚀 Deployment

### Local Testing
```bash
python app.py
```

### Production Deployment (Heroku Example)
1. Create `Procfile`:
```
web: gunicorn app:app
```

2. Update `requirements.txt` with Gunicorn:
```bash
pip install gunicorn
pip freeze > requirements.txt
```

3. Deploy:
```bash
heroku create
git push heroku main
```

---

## 📞 Support & Next Steps

### Immediate Next Steps
1. ✅ Get the site running locally (see one-minute setup)
2. 📝 Update organization contact info
3. 🖼️ Add real images (replace emoji boxes)
4. 📧 Set up email notifications for contact form
5. 🚀 Deploy to hosting platform

### Enhancement Ideas
- Add user authentication
- Create program enrollment system
- Add blog section
- Integrate payment for sponsorships
- Add video content
- Create admin dashboard
- Multi-language support

### Troubleshooting

**Port 5000 already in use?**
```bash
python app.py --port 5001
```

**Flask not found?**
```bash
pip install -r requirements.txt
```

**Animations not working?**
- Check browser console for errors
- Ensure JavaScript is enabled
- Clear browser cache

---

## 🎯 Key Features to Showcase

1. **The Revled Journey™** - Visual framework showing 0-25 path
2. **Impact Counters** - Animated metrics for engagement
3. **Program Cards** - Interactive cards for each stage
4. **Testimonials** - Social proof with success stories
5. **Color System** - Professional branding (Blue/Orange/Cream)
6. **Responsive Design** - Perfect on mobile and desktop
7. **Contact Form** - Functional backend integration
8. **Animations** - Smooth scrolling, hover effects, transitions

---

## 📖 Documentation

- **README.md** - Full technical documentation
- **app.py** - Well-commented Flask code
- **templates/** - HTML files with clear structure
- **This file** - Quick start guide

---

## ✨ Design Highlights

- **Typography**: Poppins (headings) + Inter (body)
- **Colors**: #003f87 (Deep Blue), #ff6b35 (Warm Orange), #faf8f3 (Soft Cream)
- **Layout**: Mobile-first responsive grid
- **Animations**: Fade-in on scroll, hover effects, smooth transitions
- **Icons**: Emoji-based (can be replaced with SVG/images)

---

## 🎓 Customization Examples

### Example 1: Change Program Names
```html
<!-- In templates/programs.html -->
<h2>My Custom Program Name</h2>
```

### Example 2: Update Impact Metrics
```html
<!-- In templates/impact.html -->
<div class="counter" data-target="10000">0</div> <!-- Update target number -->
```

### Example 3: Add New Section to Homepage
```html
<!-- In templates/home.html -->
<section class="section-padding px-6 bg-white">
    <div class="max-w-6xl mx-auto">
        <!-- Your new section here -->
    </div>
</section>
```

---

## 💡 Tips & Best Practices

1. **Keep content consistent** across all pages
2. **Update footer** with current contact information
3. **Test on mobile** before launching
4. **Use descriptive link text** for accessibility
5. **Keep file structure organized** for easy updates
6. **Comment code** when making changes
7. **Test forms** to ensure notifications work
8. **Monitor performance** using Lighthouse

---

**You're all set! Happy launching! 🚀**

For issues or questions, refer to README.md or update app.py directly.
