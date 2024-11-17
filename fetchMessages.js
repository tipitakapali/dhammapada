const jsonFile = "./json/dhammapada423.json";
window.onload = () => {
  fetch(jsonFile)
    .then((response) => response.json())
    .then((data) => {
      if (Array.isArray(data)) {
        createMessage(data[0]);
        let currentIndex = 1;
        const messageDelayms = 100;
        function displayNextMessage() {
          createMessage(data[currentIndex]);
          currentIndex = (currentIndex + 1) % data.length;
          setTimeout(displayNextMessage, messageDelayms);
        }
        displayNextMessage();
      }
    })
    .catch((error) => {
      console.error("Error loading messages from JSON:", error);
    });
};
