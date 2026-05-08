module.exports = {
  apps: [
    {
      name: "k-skill-proxy",
      cwd: __dirname,
      script: "./scripts/run-k-skill-proxy.sh",
      interpreter: "/bin/bash",
      exec_mode: "fork",
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: "production"
      }
    }
  ]
};
