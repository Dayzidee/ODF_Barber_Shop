document.addEventListener("DOMContentLoaded", () => {
  // Simple script to set the current year in the footer
  const currentYearSpan = document.getElementById("currentYear"); // Added this line based on previous assumption
  if (currentYearSpan) {
    // Check if the element exists
    currentYearSpan.textContent = new Date().getFullYear();
  }

  // Mobile Menu Toggle
  const mobileMenuButton = document.getElementById("mobile-menu");
  const navMenuList = document.getElementById("nav-menu-list");

  if (mobileMenuButton && navMenuList) {
    // Check if elements exist
    mobileMenuButton.addEventListener("click", () => {
      navMenuList.classList.toggle("active");
      mobileMenuButton.classList.toggle("active"); // For hamburger to "X" animation
    });

    // Optional: Close menu when a link is clicked (for one-page sites)
    const navLinks = navMenuList.querySelectorAll("a");
    navLinks.forEach((link) => {
      // 'link' is defined here for each iteration
      link.addEventListener("click", () => {
        // Close the menu
        if (navMenuList.classList.contains("active")) {
          navMenuList.classList.remove("active");
          mobileMenuButton.classList.remove("active");
        }

        // Optional: JavaScript-driven Smooth scroll (if CSS scroll-behavior is not sufficient or for more control)
        // Note: CSS `scroll-behavior: smooth;` on the `html` element is usually enough for href="#section" links.
        // If you still want JS smooth scroll, uncomment and use this:
        /*
                const targetId = link.getAttribute('href'); // 'link' is accessible here
                if (targetId && targetId.startsWith('#')) { // Ensure it's an internal link
                    const targetSection = document.querySelector(targetId);
                    if (targetSection) {
                        // Calculate offset if you have a fixed header
                        const navbarHeight = document.getElementById('navbar') ? document.getElementById('navbar').offsetHeight : 0;
                        const elementPosition = targetSection.getBoundingClientRect().top;
                        const offsetPosition = elementPosition + window.pageYOffset - navbarHeight;

                        window.scrollTo({
                            top: offsetPosition,
                            behavior: 'smooth'
                        });
                        // Or, if you don't need to account for a fixed header with JS scroll:
                        // targetSection.scrollIntoView({ behavior: 'smooth' });
                    }
                }
                */
      });
    });
  }
  // The problematic code that was outside the loop has been removed or integrated above.

  // Active Navigation Link Highlighting on Scroll
  const sections = document.querySelectorAll("section[id]");
  const navLi = document.querySelectorAll(".navbar .nav-menu li a");

  function changeActiveLink() {
    let currentSectionId = "";
    const navbarHeight = document.getElementById("navbar")
      ? document.getElementById("navbar").offsetHeight
      : 0;

    sections.forEach((section) => {
      const sectionTop = section.offsetTop - navbarHeight - 1;
      const sectionHeight = section.offsetHeight;
      if (
        window.pageYOffset >= sectionTop &&
        window.pageYOffset < sectionTop + sectionHeight
      ) {
        currentSectionId = section.getAttribute("id");
      }
    });

    if (
      window.innerHeight + window.pageYOffset >=
        document.body.offsetHeight - 50 &&
      sections.length > 0
    ) {
      currentSectionId = sections[sections.length - 1].getAttribute("id");
    }

    navLi.forEach((link) => {
      link.classList.remove("active-link");
      if (link.getAttribute("href") === "#" + currentSectionId) {
        link.classList.add("active-link");
      }
    });
  }

  // Add event listener for scroll, only if elements exist
  if (sections.length > 0 && navLi.length > 0) {
    window.addEventListener("scroll", changeActiveLink);
    window.addEventListener("load", changeActiveLink);
  }

  // --- Gallery Lightbox Functionality ---
  const galleryItems = document.querySelectorAll(".gallery-item");
  let lightbox, lightboxImg, closeButton; // Keep these declared here

  function createLightbox() {
    lightbox = document.createElement("div");
    lightbox.id = "lightbox";
    lightbox.classList.add("lightbox-overlay");
    lightboxImg = document.createElement("img");
    lightboxImg.id = "lightbox-image";
    closeButton = document.createElement("span");
    closeButton.id = "lightbox-close";
    closeButton.classList.add("lightbox-close-btn");
    closeButton.innerHTML = "×";
    lightbox.appendChild(lightboxImg);
    lightbox.appendChild(closeButton);
    document.body.appendChild(lightbox);
    closeButton.addEventListener("click", closeLightbox);
    lightbox.addEventListener("click", (e) => {
      if (e.target === lightbox) {
        closeLightbox();
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && lightbox && lightbox.style.display === "flex") {
        // Added check for lightbox existence
        closeLightbox();
      }
    });
  }

  function openLightbox(imageSrc, imageAlt) {
    if (!lightbox) {
      createLightbox();
    }
    lightboxImg.src = imageSrc;
    lightboxImg.alt = imageAlt || "Lightbox image";
    lightbox.style.display = "flex";
    document.body.style.overflow = "hidden";
  }

  function closeLightbox() {
    if (lightbox) {
      lightbox.style.display = "none";
      document.body.style.overflow = "auto";
    }
  }

  if (galleryItems.length > 0) {
    galleryItems.forEach((item) => {
      const imgElement = item.querySelector("img");
      if (imgElement) {
        item.addEventListener("click", (e) => {
          e.preventDefault();
          openLightbox(imgElement.src, imgElement.alt);
        });
      }
    });
  }
  // --- End of Gallery Lightbox ---

  // --- Basic Client-Side Form Validation ---
  const bookingForm = document.getElementById("bookingForm");

  if (bookingForm) {
    bookingForm.addEventListener("submit", function (event) {
      let isValid = true;
      const requiredInputs = bookingForm.querySelectorAll("[required]");
      const formAlert = document.getElementById("form-alert-placeholder");

      if (formAlert) formAlert.innerHTML = "";
      requiredInputs.forEach((input) => {
        input.classList.remove("input-error");
      });

      requiredInputs.forEach((input) => {
        let fieldIsEmpty = false;
        if (input.type === "checkbox") {
          if (!input.checked) fieldIsEmpty = true;
        } else if (input.type === "select-multiple") {
          if (input.selectedOptions.length === 0) fieldIsEmpty = true;
        } else {
          if (input.value.trim() === "") fieldIsEmpty = true;
        }

        if (fieldIsEmpty) {
          isValid = false;
          input.classList.add("input-error");
          const label = document.querySelector(`label[for='${input.id}']`);
          const fieldName = label
            ? label.textContent.replace("*", "").trim()
            : input.name || "A required field";

          if (formAlert) {
            const p = document.createElement("p");
            p.textContent = `Please fill out: ${fieldName}`;
            formAlert.appendChild(p);
          } else {
            console.warn(
              `Form alert placeholder not found. Missing field: ${fieldName}`
            );
          }
        }
      });

      if (!isValid) {
        event.preventDefault();
        if (formAlert && formAlert.children.length > 0) {
          formAlert.style.display = "block";
        }
        const firstError = bookingForm.querySelector(".input-error");
        if (firstError) {
          firstError.focus();
        }
      } else {
        if (formAlert) formAlert.style.display = "none";
      }
    });
  }
  // --- End of Basic Form Validation ---

  // Initialize AOS
  if (typeof AOS !== "undefined") {
    // Check if AOS is loaded
    AOS.init({
      duration: 800,
      easing: "ease-in-out",
      once: true,
      mirror: false,
      anchorPlacement: "top-bottom",
    });
  } else {
    console.warn("AOS library not found. Scroll animations will not work.");
  }
}); // End of DOMContentLoaded
