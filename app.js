// Tomb of Light Frontend JS - placeholder hooks for backend integration
// Mobile Navigation Toggle
const navToggle = document.getElementById('nav-toggle');
const navMenu = document.getElementById('nav-menu');
if (navToggle && navMenu) {
  navToggle.addEventListener('click', () => {
    navMenu.classList.toggle('open');
  });
}

// Sign-Up Form Submission
const signupForm = document.getElementById('signup-form');
if (signupForm) {
  signupForm.addEventListener('submit', function(e) {
    e.preventDefault();
    // Gather input values
    const name = document.getElementById('name').value.trim();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm_password').value;
    const agree = document.getElementById('agree').checked;
    // Basic front-end validation
    if (!name || !email || !password || !confirmPassword) {
      alert('Please fill out all required fields.');
      return;
    }
    if (!agree) {
      alert('You must agree to the Terms and Privacy Policy to sign up.');
      return;
    }
    if (password !== confirmPassword) {
      const errorEl = document.getElementById('confirm-error');
      if (errorEl) {
        errorEl.textContent = 'Passwords do not match.';
      }
      return;
    }
    // TODO: Send signup data to backend (FastAPI/Firebase/Supabase)
    console.log('Signup data:', { name, email });
    // Example: using fetch to FastAPI (commented)
    /*
    fetch('/api/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password })
    })
    .then(res => {
      if (res.ok) {
        // Redirect to sign-in or dashboard on success
        window.location.href = 'signin.html';
      } else {
        // Handle errors (e.g., show message to user)
        alert('Signup failed. Please try again.');
      }
    });
    */
    // Simulate successful signup for this demo
    alert('Account created successfully! Please sign in.');
    window.location.href = 'signin.html';
  });
}

// Sign-In Form Submission
const signinForm = document.getElementById('signin-form');
if (signinForm) {
  signinForm.addEventListener('submit', function(e) {
    e.preventDefault();
    const email = document.getElementById('signin-email').value.trim();
    const password = document.getElementById('signin-password').value;
    if (!email || !password) {
      alert('Please enter your email and password.');
      return;
    }
    // TODO: Authenticate with backend (FastAPI/Firebase/Supabase)
    console.log('Signin attempt:', { email });
    /*
    fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    })
    .then(res => {
      if (res.ok) {
        window.location.href = 'dashboard.html'; // redirect to protected area
      } else {
        alert('Invalid credentials. Please try again.');
      }
    });
    */
    // Simulate successful login for demo
    alert('Sign-in successful!');
    window.location.href = 'index.html';
  });
}

// Initialize scroll animations (AOS) if available
if (typeof AOS !== 'undefined') {
  AOS.init({ once: true });
}
