package com.virex.pro.ui

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.virex.pro.R
import com.virex.pro.VirexApp
import com.virex.pro.data.Template
import com.virex.pro.databinding.ActivityMainBinding
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val app by lazy { VirexApp.instance }

    private val templates =
            listOf(
                    // Бесплатные
                    Template("tiktok", "TikTok", "9:16, высокий битрейт", R.drawable.ic_tiktok),
                    Template(
                            "reels",
                            "Instagram Reels",
                            "Идеально для Stories",
                            R.drawable.ic_instagram
                    ),
                    Template(
                            "youtube",
                            "YouTube Shorts",
                            "Оптимизация для YT",
                            R.drawable.ic_youtube
                    ),
                    Template("clean", "Чистое видео", "Минимальная обработка", R.drawable.ic_clean),
                    // Premium - Базовые
                    Template(
                            "watermark_trap",
                            "🛡️ Watermark-Trap",
                            "Защита от детекции",
                            R.drawable.ic_process,
                            true
                    ),
                    Template(
                            "gaming",
                            "🎮 Gaming",
                            "Яркие цвета для игр",
                            R.drawable.ic_gaming,
                            true
                    ),
                    Template("vlog", "📹 Vlog", "Тёплые тона", R.drawable.ic_vlog, true),
                    Template(
                            "cinematic",
                            "🎬 Cinematic",
                            "Кинематографичный стиль",
                            R.drawable.ic_cinematic,
                            true
                    ),
                    Template(
                            "vintage",
                            "📼 Vintage",
                            "Ретро VHS эффект",
                            R.drawable.ic_vintage,
                            true
                    ),
                    Template("neon", "💜 Neon", "Неоновые цвета", R.drawable.ic_star, true),
                    Template(
                            "bw",
                            "⚫ Чёрно-белое",
                            "Классический B&W",
                            R.drawable.ic_cinematic,
                            true
                    ),
                    Template(
                            "speed",
                            "⚡ Speed Edit",
                            "Динамика и скорость",
                            R.drawable.ic_process,
                            true
                    ),
                    // Premium - Viral (Высокое качество)
                    Template(
                            "viral_4k",
                            "📺 Viral 4K",
                            "4K качество для вирусных видео",
                            R.drawable.ic_star,
                            true
                    ),
                    Template(
                            "viral_8k",
                            "🎥 Viral 8K",
                            "8K Ultra HD качество",
                            R.drawable.ic_star,
                            true
                    ),
                    Template(
                            "viral_10k",
                            "🔥 Viral 10K",
                            "10K максимальное качество",
                            R.drawable.ic_star,
                            true
                    ),
                    Template(
                            "viral_16k",
                            "👑 Viral 16K",
                            "16K экстремальное качество",
                            R.drawable.ic_star,
                            true
                    ),
                    // Premium - Уникальность
                    Template(
                            "passport",
                            "🔐 Passport",
                            "Уникальный отпечаток видео",
                            R.drawable.ic_process,
                            true
                    ),
                    Template(
                            "passport_pro",
                            "🔐 Passport PRO",
                            "Максимальная уникальность",
                            R.drawable.ic_process,
                            true
                    ),
                    // Premium - Viral эффекты
                    Template(
                            "viral_120fps",
                            "🚀 120 FPS",
                            "Плавное 120fps видео",
                            R.drawable.ic_process,
                            true
                    ),
                    Template(
                            "viral_8k_120fps",
                            "💎 8K 120FPS",
                            "8K + 120fps комбо",
                            R.drawable.ic_star,
                            true
                    ),
                    Template(
                            "avatar_style",
                            "🎭 Avatar Style",
                            "Стиль как у топ блогеров",
                            R.drawable.ic_star,
                            true
                    ),
                    Template(
                            "aesthetic_hdr",
                            "✨ Aesthetic HDR",
                            "HDR эстетика",
                            R.drawable.ic_cinematic,
                            true
                    ),
                    Template(
                            "movie_quality",
                            "🎬 Movie Quality",
                            "Кинокачество",
                            R.drawable.ic_cinematic,
                            true
                    ),
                    Template(
                            "ultra_viral",
                            "⚡ Ultra Viral",
                            "Максимум вирусности",
                            R.drawable.ic_star,
                            true
                    ),
            )

    private var selectedTemplate: Template? = null
    private var templateAdapter: TemplateAdapter? = null

    private val pickVideo =
            registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
                uri?.let { processVideo(it) }
            }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Проверяем deep link авторизацию
        handleDeepLink(intent)

        // Проверяем авторизацию
        if (!app.preferencesManager.isLoggedIn) {
            showLoginScreen()
        } else {
            showMainScreen()
            refreshSubscription()
        }

        setupViews()
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        intent?.let { handleDeepLink(it) }
    }

    private fun handleDeepLink(intent: Intent) {
        val data = intent.data ?: return

        if (data.scheme == "virexpro" && data.host == "auth") {
            val userId = data.getQueryParameter("user_id")
            val authCode = data.getQueryParameter("code")

            if (userId != null && authCode != null) {
                performAuth(userId, authCode)
            }
        }
    }

    private fun performAuth(userId: String, authCode: String) {
        lifecycleScope.launch {
            try {
                binding.progressBar.visibility = View.VISIBLE

                android.util.Log.d("VirexAuth", "Starting auth: userId=$userId")

                val response =
                        app.apiClient.api.authDeeplink(
                                mapOf("user_id" to userId, "auth_code" to authCode)
                        )

                android.util.Log.d(
                        "VirexAuth",
                        "Response: ${response.code()} ${response.message()}"
                )

                if (response.isSuccessful && response.body()?.success == true) {
                    val body = response.body()!!

                    android.util.Log.d("VirexAuth", "Auth success: ${body.user?.id}")

                    app.preferencesManager.apply {
                        this.userId = body.user?.id ?: 0
                        this.authToken = body.token
                        this.username = body.user?.username
                        this.firstName = body.user?.first_name
                        this.isPremium = body.subscription?.is_premium ?: false
                    }

                    showMainScreen()
                    refreshTemplateAdapter() // Обновляем адаптер с новым Premium статусом
                    Toast.makeText(this@MainActivity, "✅ Авторизация успешна!", Toast.LENGTH_SHORT)
                            .show()
                } else {
                    val errorBody = response.errorBody()?.string()
                    val errorMsg = response.body()?.error ?: errorBody ?: "Ошибка авторизации"
                    android.util.Log.e("VirexAuth", "Auth failed: $errorMsg; errorBody=$errorBody")
                    Toast.makeText(this@MainActivity, "❌ $errorMsg", Toast.LENGTH_LONG).show()
                }
            } catch (e: java.net.ConnectException) {
                android.util.Log.e("VirexAuth", "Connection error", e)
                Toast.makeText(
                                this@MainActivity,
                                "❌ Нет подключения к серверу.\nПроверьте что телефон и ПК в одной сети.",
                                Toast.LENGTH_LONG
                        )
                        .show()
            } catch (e: java.net.SocketTimeoutException) {
                android.util.Log.e("VirexAuth", "Timeout", e)
                Toast.makeText(this@MainActivity, "❌ Таймаут подключения", Toast.LENGTH_LONG).show()
            } catch (e: Exception) {
                android.util.Log.e("VirexAuth", "Error", e)
                Toast.makeText(this@MainActivity, "❌ Ошибка: ${e.message}", Toast.LENGTH_LONG)
                        .show()
            } finally {
                binding.progressBar.visibility = View.GONE
            }
        }
    }

    private fun showLoginScreen() {
        binding.loginLayout.visibility = View.VISIBLE
        binding.mainLayout.visibility = View.GONE

        binding.btnLoginTelegram.setOnClickListener { openTelegramBot() }

        // Кнопка для ввода кода
        binding.btnEnterCode.setOnClickListener { showCodeInputDialog() }
    }

    private fun showCodeInputDialog() {
        val editText =
                android.widget.EditText(this).apply {
                    hint = "Вставьте код: user_id:auth_code"
                    inputType = android.text.InputType.TYPE_CLASS_TEXT
                    setPadding(50, 30, 50, 30)
                }

        android.app.AlertDialog.Builder(this)
                .setTitle("Введите код авторизации")
                .setMessage("Скопируйте код из Telegram бота и вставьте сюда:")
                .setView(editText)
                .setPositiveButton("Войти") { _, _ ->
                    val code = editText.text.toString().trim()
                    if (code.contains(":")) {
                        val parts = code.split(":")
                        if (parts.size == 2) {
                            performAuth(parts[0], parts[1])
                        } else {
                            Toast.makeText(this, "Неверный формат кода", Toast.LENGTH_SHORT).show()
                        }
                    } else {
                        Toast.makeText(this, "Неверный формат кода", Toast.LENGTH_SHORT).show()
                    }
                }
                .setNegativeButton("Отмена", null)
                .show()
    }

    private fun showMainScreen() {
        binding.loginLayout.visibility = View.GONE
        binding.mainLayout.visibility = View.VISIBLE

        updateUserInfo()
    }

    private fun setupViews() {
        // Настройка списка шаблонов
        setupTemplateAdapter()

        // Выбор видео
        binding.btnSelectVideo.setOnClickListener {
            if (selectedTemplate == null) {
                Toast.makeText(this, "Выберите шаблон", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            pickVideo.launch("video/*")
        }

        // Подписка
        binding.btnSubscription.setOnClickListener {
            startActivity(Intent(this, SubscriptionActivity::class.java))
        }

        // История
        binding.btnHistory.setOnClickListener {
            startActivity(Intent(this, HistoryActivity::class.java))
        }

        // Настройки
        binding.btnSettings.setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }

        // Выход
        binding.btnLogout.setOnClickListener {
            app.preferencesManager.logout()
            showLoginScreen()
        }
    }

    private fun setupTemplateAdapter() {
        templateAdapter =
                TemplateAdapter(templates, app.preferencesManager.isPremium) { template ->
                    selectedTemplate = template
                    app.preferencesManager.lastTemplate = template.id
                }
        binding.rvTemplates.adapter = templateAdapter
    }

    private fun refreshTemplateAdapter() {
        // Пересоздаём адаптер с актуальным isPremium
        setupTemplateAdapter()
    }

    private fun openTelegramBot() {
        val botUsername = "Virexprobot" // Замените на username вашего бота

        // Пробуем открыть в Telegram
        try {
            val intent =
                    Intent(
                            Intent.ACTION_VIEW,
                            Uri.parse("tg://resolve?domain=$botUsername&start=app_auth")
                    )
            startActivity(intent)
        } catch (e: Exception) {
            // Fallback на веб-версию
            val intent =
                    Intent(
                            Intent.ACTION_VIEW,
                            Uri.parse("https://t.me/$botUsername?start=app_auth")
                    )
            startActivity(intent)
        }
    }

    private fun updateUserInfo() {
        val name = app.preferencesManager.firstName ?: app.preferencesManager.username ?: "User"
        binding.tvUserName.text = "Привет, $name! 👋"

        if (app.preferencesManager.isPremium) {
            binding.tvSubscription.text = "⭐ Premium"
            binding.tvSubscription.setTextColor(getColor(R.color.premium_gold))
        } else {
            binding.tvSubscription.text = "Free"
            binding.tvSubscription.setTextColor(getColor(R.color.text_secondary))
        }

        binding.tvVideosCount.text = "• ${app.preferencesManager.totalVideos} видео"
    }

    private fun refreshSubscription() {
        lifecycleScope.launch {
            try {
                val response =
                        app.apiClient.api.getSubscription(
                                app.preferencesManager.userId.toString(),
                                app.preferencesManager.authToken ?: ""
                        )

                if (response.isSuccessful) {
                    response.body()?.let { sub ->
                        val wasPremium = app.preferencesManager.isPremium
                        app.preferencesManager.isPremium = sub.is_premium
                        app.preferencesManager.totalVideos = sub.total_videos
                        updateUserInfo()

                        // Обновляем адаптер если статус изменился
                        if (wasPremium != sub.is_premium) {
                            refreshTemplateAdapter()
                        }
                    }
                }
            } catch (e: Exception) {
                // Игнорируем ошибку обновления
            }
        }
    }

    private fun processVideo(videoUri: Uri) {
        val intent =
                Intent(this, ProcessActivity::class.java).apply {
                    putExtra(ProcessActivity.EXTRA_VIDEO_URI, videoUri.toString())
                    putExtra(ProcessActivity.EXTRA_TEMPLATE, selectedTemplate?.id ?: "tiktok")
                }
        startActivity(intent)
    }
}
