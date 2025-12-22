# 🌸 Shizu Discord Bot

A feature-rich Discord bot with fun commands, moderation tools, music playback, AI chat integration, and an extensive economy/pet system.

## ✨ Features

### 🎮 Fun & Games
- **Pet System** - Catch, collect, and battle with pets
- **Economy System** - Earn currency, shop for items, and manage your balance
- **Games** - Trivia, UNO, guessing games, gambling, and more
- **Interactions** - Hug, kiss, pat, and other social interactions with custom emojis
- **Marriage System** - Propose and marry other users
- **Shipping** - Check compatibility between users
- **Memes** - Generate and share memes
- **Snipe** - Recover deleted/edited messages

### 🎵 Music
- **Music Playback** - Play music from YouTube and Spotify
- **Queue Management** - Add, skip, and manage your music queue
- **Volume Control** - Adjust playback volume
- **Auto-play** - Automatic song recommendations

### 🛠️ Utility
- **AI Chat** - Integrated AI chatbot powered by Ollama with customizable personalities
- **Quote Generator** - Create beautiful quote images with user avatars
- **Server Info** - Display detailed server information
- **User Info** - View user profiles and statistics
- **Giveaways** - Host and manage giveaways
- **Welcome System** - Customizable welcome messages for new members

### 🔨 Moderation
- **Ban/Unban** - Permanent ban management
- **Kick** - Remove users from the server
- **Mute** - Mute users in chat
- **Timeout** - Temporarily timeout users
- **Temp Ban** - Temporary ban with auto-unban
- **Purge** - Bulk delete messages
- **Role Management** - Assign and remove roles
- **Restrict** - Restrict users from using the bot or chatting

### 👑 Admin
- **Superuser System** - Bot owner and whitelisted users can bypass all permission checks
- **Command Syncing** - Sync slash commands globally
- **Avatar Management** - Change bot avatar

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- Discord Bot Token ([Create one here](https://discord.com/developers/applications))
- FFmpeg (for music playback)
- Ollama (optional, for AI chat features)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/shizu.git
   cd shizu
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   
   Create a `.env` file in the root directory:
   ```env
   DISCORD_TOKEN=your_discord_bot_token_here
   SPOTIFY_CLIENT_ID=your_spotify_client_id
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
   YOUTUBE_API_KEY=your_youtube_api_key
   OLLAMA_API_URL=http://localhost:11434
   ```

4. **Create required directories**
   ```bash
   mkdir data logs downloaded_avatars fonts
   ```

5. **Run the bot**
   ```bash
   python main.py
   ```

## 📁 Project Structure

```
Shizu/
├── cogs/
│   ├── fun/              # Fun commands and games
│   ├── utility/          # Utility commands
│   ├── moderation/       # Moderation commands
│   └── utils/            # Shared utilities and checks
├── data/                 # Bot data (gitignored)
├── fonts/                # Fonts for image generation
├── logs/                 # Log files (gitignored)
├── main.py               # Bot entry point
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (gitignored)
└── README.md            # This file
```

## 🎯 Usage

The bot uses Discord's slash commands. After inviting the bot to your server, use `/` to see all available commands.

### Example Commands
- `/catch` - Catch a pet when one spawns
- `/balance` - Check your economy balance
- `/play <song>` - Play music in a voice channel
- `/quote @user <text>` - Generate a quote image
- `/trivia` - Start a trivia game
- `/hug @user` - Hug another user
- `/ban @user <reason>` - Ban a user (requires permissions)

## ⚙️ Configuration

### Superuser System
The bot owner and whitelisted users can bypass all permission checks. Manage superusers with:
- `/addsuperuser @user` - Add a superuser
- `/removesuperuser @user` - Remove a superuser
- `/listsuperusers` - List all superusers

### AI Chat
Configure AI chat personalities per server using the AI chat commands. Requires Ollama to be running.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- Built with [discord.py](https://github.com/Rapptz/discord.py)
- Music playback powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- AI chat powered by [Ollama](https://ollama.ai/)

## 📧 Support

If you encounter any issues or have questions, please open an issue on GitHub.

---

Made with ❤️ by EndSkiess
