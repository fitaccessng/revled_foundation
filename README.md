# Revled Foundation Website

A modern, interactive website for Revled Foundation - a youth development organization focused on nurturing emotionally intelligent, skilled, and purpose-driven young people in Nigeria.

## Project Overview

**The Revled Journey™** - A structured path from childhood learning to economic independence, spanning ages 0-25 with four distinct program stages:

- **Revled Roots** (0-8): Foundation building through play and emotional awareness
- **Revled Explorers** (8-13): Discovery and skill development
- **Revled Catalyst** (13-17): Leadership and character building
- **Revled Launchpad** (17-25): Career development and economic independence

## Tech Stack

- **Frontend**: HTML5 + Tailwind CSS
- **Backend**: Python Flask with Jinja2 templating
- **Styling**: Responsive design with animations
- **Features**: Contact forms, dynamic routing, flash messages

## Project Structure

```
revled.org/
├── app.py                 # Flask application with all routes
├── requirements.txt       # Python dependencies
├── templates/
│   ├── base.html         # Base template with navbar/footer
│   ├── home.html         # Homepage
│   ├── about.html        # About page
│   ├── programs.html     # Programs showcase
│   ├── impact.html       # Impact metrics & stories
│   ├── get-involved.html # Partnership opportunities
│   ├── resources.html    # Learning materials
│   ├── contact.html      # Contact form & info
│   ├── 404.html          # 404 error page
│   ├── 500.html          # 500 error page
│   └── components/
│       ├── navbar.html   # Navigation component
│       └── footer.html   # Footer component
└── static/
    ├── css/
    │   └── style.css     # Custom styles
    └── js/
        └── animations.js # Scroll & interaction animations
```

## Features

### Pages

1. **Homepage** - Hero section, visual journey framework, impact metrics, testimonials, CTA
2. **About** - Organization story, vision/mission, core values, the Revled model (0-25)
3. **Programs** - Detailed breakdown of each stage with features and benefits
4. **Impact** - Metrics, transformation stories, community reach, outcomes
5. **Get Involved** - Partnership tiers, sponsorship options, volunteering
6. **Resources** - Storybooks, educational videos, parent guides, learning materials
7. **Contact** - Contact form with backend processing, FAQ, location info

### Design Elements

- ✨ **Color Scheme**: Deep Blue (trust), Warm Orange (creativity), Soft Cream (background)
- 🎨 **Animations**: Fade-in on scroll, hover effects, smooth transitions
- 📱 **Responsive**: Mobile-first design, optimized for all screen sizes
- ⚡ **Performance**: Lightweight CSS, minimal JavaScript
- ♿ **Accessibility**: Semantic HTML, focus states, reduced motion support

### Interactive Features

- Mobile-responsive hamburger menu
- Scroll-triggered section animations
- Animated counters for impact metrics
- Contact form with validation
- Card hover effects and micro-interactions
- Smooth scrolling navigation
- Scroll-to-top button

## Getting Started

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Installation

1. **Clone/Navigate to the project**:
   ```bash
   cd /Users/macbookpro/Documents/revled.org
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python app.py
   ```

5. **Open in browser**:
   ```
   http://localhost:5000
   ```

## Routes

| Route | Template | Description |
|-------|----------|-------------|
| `/` | `home.html` | Homepage |
| `/about` | `about.html` | Organization information |
| `/programs` | `programs.html` | All programs (0-25) |
| `/impact` | `impact.html` | Impact metrics & stories |
| `/get-involved` | `get-involved.html` | Partnership opportunities |
| `/resources` | `resources.html` | Learning materials |
| `/contact` | `contact.html` | Contact form & information |

## Customization

### Colors

Edit the CSS variables in `base.html`:

```css
--deep-blue: #003f87;      /* Primary color */
--warm-orange: #ff6b35;    /* Accent color */
--soft-cream: #faf8f3;     /* Background */
```

### Content

Each page's content is stored in its corresponding HTML template in the `templates/` folder. Edit directly to update text, images, or structure.

### Forms

Contact form submissions are handled in `app.py`. Currently, submissions generate flash messages. To enable email sending:

1. Configure email settings in `app.py`
2. Add email library (e.g., Flask-Mail)
3. Update the contact route to send emails

## Production Deployment

Before deploying to production:

1. **Update SECRET_KEY** in `app.py`:
   ```python
   app.secret_key = os.environ.get('SECRET_KEY', 'production-secret-key')
   ```

2. **Set Debug Mode to False**:
   ```python
   app.run(debug=False)
   ```

3. **Use a production WSGI server** (e.g., Gunicorn):
   ```bash
   pip install gunicorn
   gunicorn -w 4 app:app
   ```

4. **Set up environment variables** for sensitive data

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

## Performance

- **Lighthouse Score Target**: 90+
- **Page Load Time**: < 2 seconds
- **Responsive**: Mobile-first, optimized for all devices
- **Accessibility**: WCAG 2.1 AA compliant

## Future Enhancements

- [ ] User authentication system
- [ ] Program enrollment functionality
- [ ] Blog/news section
- [ ] Integration with email service
- [ ] Database for storing inquiries
- [ ] Analytics tracking
- [ ] Multi-language support
- [ ] Social media integration
- [ ] Event calendar
- [ ] Donation gateway integration

## Support

For issues or questions:
- Email: hello@revled.org
- Phone: +234 701 234 5678

## License

© 2024 Revled Foundation. All rights reserved.

---

**Built with ❤️ for youth development in Nigeria**
