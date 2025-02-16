document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // Form validation
    const checkInForm = document.getElementById('checkInForm');
    const checkOutForm = document.getElementById('checkOutForm');

    if (checkInForm) {
        checkInForm.addEventListener('submit', function(event) {
            const plateNumber = document.getElementById('plateNumber').value;
            if (!plateNumber.match(/^[A-Za-z0-9]{3,10}$/)) {
                event.preventDefault();
                alert('Please enter a valid plate number (3-10 alphanumeric characters)');
            }
        });
    }

    if (checkOutForm) {
        checkOutForm.addEventListener('submit', function(event) {
            const plateNumber = document.getElementById('checkOutPlateNumber').value;
            if (!plateNumber.match(/^[A-Za-z0-9]{3,10}$/)) {
                event.preventDefault();
                alert('Please enter a valid plate number (3-10 alphanumeric characters)');
            }
        });
    }

    // Auto-dismiss alerts after 3 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.classList.add('fade');
            setTimeout(() => alert.remove(), 150);
        }, 3000);
    });
});