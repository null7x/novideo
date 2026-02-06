package com.virex.pro.ui

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.virex.pro.VirexApp
import com.virex.pro.databinding.ActivitySettingsBinding
import kotlinx.coroutines.launch

class SettingsActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySettingsBinding
    private val app by lazy { VirexApp.instance }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupViews()
        loadSettings()
    }

    private fun setupViews() {
        binding.toolbar.setNavigationOnClickListener { finish() }

        // Сохранение настроек сервера
        binding.btnSaveServer.setOnClickListener {
            val serverUrl = binding.etServerUrl.text.toString().trim()
            if (serverUrl.isEmpty()) {
                Toast.makeText(this, "Введите URL сервера", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            // Проверяем формат URL
            if (!serverUrl.startsWith("http://") && !serverUrl.startsWith("https://")) {
                Toast.makeText(
                                this,
                                "URL должен начинаться с http:// или https://",
                                Toast.LENGTH_SHORT
                        )
                        .show()
                return@setOnClickListener
            }

            app.preferencesManager.serverUrl = serverUrl.trimEnd('/')
            Toast.makeText(this, "✅ Сервер сохранён", Toast.LENGTH_SHORT).show()

            // Проверяем подключение
            testConnection()
        }

        // Проверка подключения
        binding.btnTestConnection.setOnClickListener { testConnection() }

        // Сброс на стандартный сервер
        binding.btnResetServer.setOnClickListener {
            binding.etServerUrl.setText(com.virex.pro.data.PreferencesManager.DEFAULT_SERVER_URL)
            app.preferencesManager.serverUrl =
                    com.virex.pro.data.PreferencesManager.DEFAULT_SERVER_URL
            Toast.makeText(this, "URL сброшен на стандартный", Toast.LENGTH_SHORT).show()
        }

        // Очистка кэша
        binding.btnClearCache.setOnClickListener { clearCache() }

        // Поддержка
        binding.btnSupport.setOnClickListener { openTelegramBot() }

        // О приложении
        binding.btnAbout.setOnClickListener { showAboutDialog() }
    }

    private fun loadSettings() {
        binding.etServerUrl.setText(app.preferencesManager.serverUrl)

        // Показываем статистику
        binding.tvTotalVideos.text = "Обработано видео: ${app.preferencesManager.totalVideos}"

        // Показываем информацию о пользователе
        if (app.preferencesManager.isLoggedIn) {
            val name = app.preferencesManager.firstName ?: app.preferencesManager.username ?: "User"
            binding.tvUserInfo.text = "👤 $name (ID: ${app.preferencesManager.userId})"

            if (app.preferencesManager.isPremium) {
                binding.tvSubscriptionStatus.text = "⭐ Premium активен"
                binding.tvSubscriptionStatus.setTextColor(
                        getColor(com.virex.pro.R.color.premium_gold)
                )
            } else {
                binding.tvSubscriptionStatus.text = "Free версия"
                binding.tvSubscriptionStatus.setTextColor(
                        getColor(com.virex.pro.R.color.text_secondary)
                )
            }
        } else {
            binding.tvUserInfo.text = "Не авторизован"
            binding.tvSubscriptionStatus.text = ""
        }

        // Показываем размер кэша
        updateCacheSize()
    }

    private fun testConnection() {
        binding.tvConnectionStatus.text = "⏳ Проверка..."
        binding.tvConnectionStatus.setTextColor(getColor(com.virex.pro.R.color.text_secondary))

        lifecycleScope.launch {
            try {
                val response = app.apiClient.api.healthCheck()
                if (response.isSuccessful) {
                    binding.tvConnectionStatus.text = "✅ Подключено"
                    binding.tvConnectionStatus.setTextColor(getColor(com.virex.pro.R.color.success))
                } else {
                    binding.tvConnectionStatus.text = "❌ Ошибка: ${response.code()}"
                    binding.tvConnectionStatus.setTextColor(getColor(com.virex.pro.R.color.error))
                }
            } catch (e: java.net.ConnectException) {
                binding.tvConnectionStatus.text = "❌ Нет подключения к серверу"
                binding.tvConnectionStatus.setTextColor(getColor(com.virex.pro.R.color.error))
            } catch (e: java.net.SocketTimeoutException) {
                binding.tvConnectionStatus.text = "❌ Таймаут подключения"
                binding.tvConnectionStatus.setTextColor(getColor(com.virex.pro.R.color.error))
            } catch (e: Exception) {
                binding.tvConnectionStatus.text = "❌ ${e.message}"
                binding.tvConnectionStatus.setTextColor(getColor(com.virex.pro.R.color.error))
            }
        }
    }

    private fun clearCache() {
        try {
            cacheDir.deleteRecursively()
            cacheDir.mkdirs()
            Toast.makeText(this, "✅ Кэш очищен", Toast.LENGTH_SHORT).show()
            updateCacheSize()
        } catch (e: Exception) {
            Toast.makeText(this, "❌ Ошибка: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun updateCacheSize() {
        val cacheSize = getCacheDirSize()
        binding.tvCacheSize.text = "Размер кэша: ${formatFileSize(cacheSize)}"
    }

    private fun getCacheDirSize(): Long {
        var size = 0L
        cacheDir.walkTopDown().forEach { file ->
            if (file.isFile) {
                size += file.length()
            }
        }
        return size
    }

    private fun formatFileSize(size: Long): String {
        return when {
            size < 1024 -> "$size B"
            size < 1024 * 1024 -> "${size / 1024} KB"
            size < 1024 * 1024 * 1024 -> "${size / 1024 / 1024} MB"
            else -> "${size / 1024 / 1024 / 1024} GB"
        }
    }

    private fun openTelegramBot() {
        val botUsername = "Virexprobot"
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("tg://resolve?domain=$botUsername")))
        } catch (e: Exception) {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://t.me/$botUsername")))
        }
    }

    private fun showAboutDialog() {
        android.app.AlertDialog.Builder(this)
                .setTitle("О приложении")
                .setMessage(
                        """
                VIREX PRO v1.0.0
                
                Уникализация видео для:
                • TikTok
                • Instagram Reels
                • YouTube Shorts
                
                Функции:
                ✓ 12 шаблонов обработки
                ✓ Watermark-Trap защита
                ✓ Удаление метаданных
                ✓ Уникальные фильтры
                
                © 2025 VIREX PRO
            """.trimIndent()
                )
                .setPositiveButton("OK", null)
                .show()
    }
}
