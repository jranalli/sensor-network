$(document).ready(function() {
    // Step 1: Get the dropdown element and add an event listener
    $('#categoryDropdown').change(function() {
        // Get the selected value
        var selectedValue = $(this).val();
        var selectedText = $(this).find("option:selected").text();

        // Step 3: Use jQuery Ajax to send POST request
        $.ajax({
            url: '/dashboard',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ category: selectedText }),
            dataType: 'json',
            success: function(response) {
                // Step 4: Handle the response
                console.log('Success:', response);
                // Optionally, update the UI here based on the response
                if (response.redirect_url) {
                    window.location.href = response.redirect_url;
                } else {
                    console.log('Success:', response);
                }
            },
            error: function(error) {
                console.error('Error:', error);
            }
        });
    });
});