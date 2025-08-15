function hey(e) {
    const API_URL = "https://9a51c5faced2.ngrok-free.app/api/submit";
    
    try {
      // 1. Get form data (same method as onSubmit)
      const responses = e.response.getItemResponses();
      const usernameResponse = responses.find(r => r.getItem().getTitle() === "Victim (login)");
      
      if (!usernameResponse) throw new Error("Question 'Victim (login)' not found");
      
      const formData = {
        login: usernameResponse.getResponse()
      };
      
      console.log("Prepared data:", JSON.stringify(formData));
  
      // 2. Send to API
      const options = {
        method: "POST",
        contentType: "application/json",
        payload: JSON.stringify(formData),
        muteHttpExceptions: true,
        timeout: 30000
      };
  
      const response = UrlFetchApp.fetch(API_URL, options);
      const data = JSON.parse(response.getContentText());
      console.log("API Response:", data);
  
      // 3. Return success message
      return "Dashboard will open shortly for " + formData.login;
      
    } catch (error) {
      console.error("Error:", error);
      return "Error: " + error.toString();
    }
  }