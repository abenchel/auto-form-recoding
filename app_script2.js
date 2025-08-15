function onSubmit(e) {
    const API_URL = "https://9a51c5faced2.ngrok-free.app/api/data";
    
    // Debug: Afficher l'objet complet des réponses
    console.log("Toutes les réponses:", JSON.stringify(e.response.getItemResponses().map(r => ({
      question: r.getItem().getTitle(),
      response: r.getResponse()
    }))));
  
    try {
      // 1. Récupérer les données du formulaire avec vérification
      const responses = e.response.getItemResponses();
      
      const usernameResponse = responses.find(r => r.getItem().getTitle() === "Victim (login)");
      const daysResponse = responses.find(r => r.getItem().getTitle() === "failed days");
      
      if (!usernameResponse) throw new Error("Question 'Victim (login)' non trouvée");
      
      let formData = {
        username: usernameResponse.getResponse(),
        days: daysResponse ? daysResponse.getResponse() : []
      };
      
      console.log("Données préparées:", JSON.stringify(formData));
  
      // 2. Envoyer à l'API
      const options = {
        method: "POST",
        contentType: "application/json",
        payload: JSON.stringify(formData),
        muteHttpExceptions: true,
        timeout: 30000 // 30 secondes timeout
      };
  
      const response = UrlFetchApp.fetch(API_URL, options);
      console.log("Réponse API:", response.getContentText());
      
      // Envoyer un email de confirmation
      MailApp.sendEmail(
        Session.getActiveUser().getEmail(), 
        "Données envoyées", 
        `Données pour ${formData.username} reçues.\nJours: ${formData.days.join(", ")}`
      );
      
      return "Succès";
      
    } catch (error) {
      console.error("Erreur complète:", error);
      MailApp.sendEmail(
        Session.getActiveUser().getEmail(),
        "ERREUR: Échec d'envoi",
        `Détails: ${error.toString()}`
      );
      throw error; // Pour voir l'erreur dans les logs
    }
  }