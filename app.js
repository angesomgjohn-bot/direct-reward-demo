let balance = 0;
let rewards = 0;
let refcount = 0;

function showLogin() {
  document.getElementById("register").hidden = true;
  document.getElementById("login").hidden = false;
}

function showRegister() {
  document.getElementById("login").hidden = true;
  document.getElementById("register").hidden = false;
}

function register() {

  const name = document.getElementById("regName").value.trim();
  const phone = document.getElementById("regPhone").value.trim();
  const password = document.getElementById("regPassword").value;
  const confirm = document.getElementById("regConfirm").value;

  const message = document.getElementById("registerMessage");

  if (!name || !phone || !password || !confirm) {
    message.textContent = "እባክዎ ሁሉንም ቦታ ይሙሉ።";
    return;
  }

  if (password.length < 6) {
    message.textContent = "ፓስዎርድ ቢያንስ 6 ቁምፊ ይኑረው።";
    return;
  }

  if (password !== confirm) {
    message.textContent = "ፓስዎርድ እና Confirm Password አይመሳሰሉም።";
    return;
  }

  const existingUser = localStorage.getItem("directRewardUser");

  if (existingUser) {
    const user = JSON.parse(existingUser);

    if (user.phone === phone) {
      message.textContent = "ይህ ስልክ ቁጥር ቀድሞ ተመዝግቧል።";
      return;
    }
  }

  const user = {
    name: name,
    phone: phone,
    password: password
  };

  localStorage.setItem("directRewardUser", JSON.stringify(user));

  message.textContent = "Registration successful!";

  setTimeout(() => {
    showLogin();
  }, 800);
}


function login() {

  const phone = document.getElementById("loginPhone").value.trim();
  const password = document.getElementById("loginPassword").value;

  const message = document.getElementById("loginMessage");

  const savedUser = localStorage.getItem("directRewardUser");

  if (!savedUser) {
    message.textContent = "እባክዎ መጀመሪያ Register ያድርጉ።";
    return;
  }

  const user = JSON.parse(savedUser);

  if (phone !== user.phone || password !== user.password) {
    message.textContent = "ስልክ ቁጥር ወይም ፓስዎርድ ትክክል አይደለም።";
    return;
  }

  document.getElementById("register").hidden = true;
  document.getElementById("login").hidden = true;
  document.getElementById("dashboard").hidden = false;

  document.getElementById("welcome").textContent =
    "Welcome, " + user.name + "!";

  render();
}


function render() {

  document.getElementById("balance").textContent =
    balance.toLocaleString() + " ETB";

  document.getElementById("rewards").textContent =
    rewards.toLocaleString() + " ETB";

  document.getElementById("refcount").textContent =
    refcount;
}


function logout() {

  document.getElementById("dashboard").hidden = true;
  document.getElementById("login").hidden = false;

  document.getElementById("loginPhone").value = "";
  document.getElementById("loginPassword").value = "";
}
