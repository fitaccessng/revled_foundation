# Revled Foundation Website Setup Instructions

## 🎯 Complete Installation & Setup

### Step 1: Verify Python Installation

```bash
python3 --version  # Should be 3.8 or higher
```

### Step 2: Navigate to Project Directory

```bash
cd /Users/macbookpro/Documents/revled.org
```

### Step 3: Create Virtual Environment

```bash
python3 -m venv venv
```

### Step 4: Activate Virtual Environment

```bash
# macOS/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### Step 5: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 6: Run the Application

```bash
python app.py
```

### Step 7: Access the Website

Open your browser and go to:
```
http://localhost:5000
```

---

## ✅ What You Should See

1. **Navigation Bar** - Links to all pages (Home, About, Programs, Impact, etc.)
2. **Homepage** - Hero section with "Nurture Tomorrow's Leaders Today"
3. **Fully Styled Pages** - All with:
   - Color scheme (Deep Blue, Warm Orange, Soft Cream)
   - Responsive layout
   - Smooth animations
   - Professional styling

---

## 🔧 Configuration Options

### Change Development Port

Edit `app.py` (last line):
```python
if __name__ == '__main__':
    app.run(debug=True, port=5001)  # Change port here
```

### Enable/Disable Debug Mode

For **development** (debug ON):
```python
app.run(debug=True)
```

For **production** (debug OFF):
```python
app.run(debug=False)
```

### Set Secret Key for Production

Create a `.env` file:
```bash
echo "SECRET_KEY=your-production-secret-key-here" > .env
```

Then in `app.py`:
```python
from dotenv import load_dotenv
load_dotenv()

app.secret_key = os.environ.get('SECRET_KEY')
```

---

## 🧪 Testing the Website

### Test All Pages
- [ ] Homepage - Check hero, journey visual, impact counters
- [ ] About - Verify story and Revled model sections
- [ ] Programs - Review all 4 program stages
- [ ] Impact - Check animated counters
- [ ] Get Involved - Test sponsorship tiers
- [ ] Resources - Review learning materials
- [ ] Contact - Test contact form submission

### Test Responsiveness
- [ ] Desktop (1920px)
- [ ] Tablet (768px)
- [ ] Mobile (375px)

Use Chrome DevTools: `F12` → Toggle device toolbar (Ctrl+Shift+M)

### Test Forms
- Contact form submission
- Form validation
- Flash messages display

---

## 📧 Enable Email Notifications (Optional)

To receive contact form submissions via email:

### 1. Install Flask-Mail

```bash
pip install Flask-Mail
```

### 2. Update requirements.txt

```bash
pip freeze > requirements.txt
```

### 3. Configure in app.py

Add before the Flask app initialization:
```python
from flask_mail import Mail, Message

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your-app-password'

mail = Mail(app)
```

### 4. Update Contact Route

Replace the contact route in `app.py` with:
```python
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message_text = request.form.get('message', '').strip()
        
        if not all([name, email, subject, message_text]):
            flash('Please fill in all fields.', 'error')
        elif len(message_text) < 10:
            flash('Message must be at least 10 characters.', 'error')
        else:
            try:
                msg = Message(
                    subject=f"New Contact: {subject}",
                    body=f"From: {name}\nEmail: {email}\n\nMessage:\n{message_text}",
                    recipients=['hello@revled.org']
                )
                mail.send(msg)
                flash(f'Thank you {name}! We\'ll get back to you soon.', 'success')
                return redirect(url_for('contact'))
            except Exception as e:
                flash('Error sending message. Please try again.', 'error')
    
    return render_template('contact.html')
```

---

## 🚀 Deployment Options

### Option 1: Heroku (Free with limitations)

```bash
# 1. Create Procfile
echo "web: gunicorn app:app" > Procfile

# 2. Add Gunicorn
pip install gunicorn
pip freeze > requirements.txt

# 3. Initialize Git (if not already)
git init
git add .
git commit -m "Initial commit"

# 4. Create Heroku app
heroku create your-app-name

# 5. Deploy
git push heroku main
```

### Option 2: PythonAnywhere

1. Sign up at https://www.pythonanywhere.com
2. Upload your files
3. Configure web app settings
4. Set Python version and WSGI file

### Option 3: AWS, Azure, Google Cloud

All support Flask applications. Follow their respective Python app deployment guides.

---

## 📦 Project Dependencies

Current dependencies in `requirements.txt`:

- **Flask** (3.0.0) - Web framework
- **Werkzeug** (3.0.1) - WSGI utilities
- **python-dotenv** (1.0.0) - Environment variables

Optional for production:
- **gunicorn** - Production server
- **Flask-Mail** - Email support
- **python-dotenv** - Environment configuration

---

## 🛠️ Development Tools

### Code Editor
- VS Code with Python extension recommended
- Or any text editor (Sublime, PyCharm, etc.)

### Browser DevTools
Press `F12` to open:
- Inspect elements
- Debug JavaScript
- Check responsive design
- Monitor network requests

### Python Debugging

Add breakpoints in `app.py`:
```python
import pdb
pdb.set_trace()  # Execution pauses here
```

Or use Flask shell:
```bash
export FLASK_APP=app.py
flask shell
```

---

## 📝 Common Issues & Solutions

### Issue: "Port 5000 already in use"
**Solution:**
```bash
python app.py --port 5001
```

### Issue: "ModuleNotFoundError: No module named 'flask'"
**Solution:**
```bash
source venv/bin/activate  # Activate virtual environment
pip install -r requirements.txt
```

### Issue: "No module named 'flask_mail'"
**Solution:**
```bash
pip install Flask-Mail
```

### Issue: Contact form not sending emails
**Solution:**
- Verify SMTP settings
- Check email credentials
- Allow "Less secure apps" (Gmail)
- Check spam folder

### Issue: Static files not loading
**Solution:**
Clear browser cache (Ctrl+Shift+Delete) and refresh

---

## 📊 Monitoring & Analytics

### Add Google Analytics
Add to `templates/base.html` before `</body>`:
```html
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=GA_MEASUREMENT_ID"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'GA_MEASUREMENT_ID');
</script>
```

Replace `GA_MEASUREMENT_ID` with your Google Analytics ID.

---

## 🔐 Security Checklist

Before deploying to production:

- [ ] Change `SECRET_KEY` in `app.py`
- [ ] Set `debug=False`
- [ ] Validate all user inputs
- [ ] Use HTTPS only
- [ ] Keep dependencies updated
- [ ] Add CSRF protection if needed
- [ ] Sanitize email addresses
- [ ] Use environment variables for sensitive data
- [ ] Set up proper error logging
- [ ] Regular security audits

---

## 📞 Support

If you encounter issues:

1. Check the README.md for detailed documentation
2. Review QUICKSTART.md for common tasks
3. Check app.py for inline comments
4. Test in development mode first
5. Check browser console for errors (F12)

---

## ✨ Next Steps

1. ✅ Get running locally (follow installation above)
2. ✅ Customize with real content
3. ✅ Add real images
4. ✅ Set up email notifications
5. ✅ Test thoroughly
6. ✅ Deploy to production
7. ✅ Monitor performance
8. ✅ Gather feedback
9. ✅ Iterate and improve

---

**Happy developing! 🚀**
