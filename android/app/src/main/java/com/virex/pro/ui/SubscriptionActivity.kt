package com.virex.pro.ui

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.virex.pro.VirexApp
import com.virex.pro.databinding.ActivitySubscriptionBinding
import kotlinx.coroutines.launch

class SubscriptionActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySubscriptionBinding
    private val app by lazy { VirexApp.instance }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySubscriptionBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupViews()
        updateUI()
        refreshSubscription()
    }

    private fun setupViews() {
        binding.toolbar.setNavigationOnClickListener { finish() }

        // Кнопка покупки подписки через Telegram
        binding.btnBuyWeek.setOnClickListener { openTelegramPayment("week") }
        binding.btnBuyMonth.setOnClickListener { openTelegramPayment("month") }
        binding.btnBuyYear.setOnClickListener { openTelegramPayment("year") }
        binding.btnBuyForever.setOnClickListener { openTelegramPayment("forever") }
    }

    private fun updateUI() {
        if (app.preferencesManager.isPremium) {
            binding.tvCurrentStatus.text = "⭐ Premium активен"
            binding.tvCurrentStatus.setTextColor(getColor(com.virex.pro.R.color.premium_gold))

            val expires = app.preferencesManager.subscriptionExpires
            if (expires > 0) {
                val date =
                        java.text.SimpleDateFormat("dd.MM.yyyy", java.util.Locale.getDefault())
                                .format(java.util.Date(expires * 1000))
                binding.tvExpires.text = "Действует до: $date"
                binding.tvExpires.visibility = android.view.View.VISIBLE
            } else {
                binding.tvExpires.text = "Навсегда ∞"
                binding.tvExpires.visibility = android.view.View.VISIBLE
            }

            // Скрываем кнопки покупки для Premium
            binding.btnBuyWeek.alpha = 0.5f
            binding.btnBuyMonth.alpha = 0.5f
            binding.btnBuyYear.alpha = 0.5f
            binding.btnBuyForever.alpha = 0.5f
        } else {
            binding.tvCurrentStatus.text = "Free"
            binding.tvExpires.visibility = android.view.View.GONE

            // Показываем кнопки покупки
            binding.btnBuyWeek.alpha = 1.0f
            binding.btnBuyMonth.alpha = 1.0f
            binding.btnBuyYear.alpha = 1.0f
            binding.btnBuyForever.alpha = 1.0f
        }
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
                        app.preferencesManager.isPremium = sub.is_premium
                        app.preferencesManager.totalVideos = sub.total_videos
                        sub.subscription?.expires?.let {
                            app.preferencesManager.subscriptionExpires = it
                        }
                        updateUI()
                    }
                }
            } catch (e: Exception) {
                // Игнорируем ошибку
            }
        }
    }

    private fun openTelegramPayment(plan: String) {
        if (app.preferencesManager.isPremium) {
            Toast.makeText(this, "У вас уже есть Premium!", Toast.LENGTH_SHORT).show()
            return
        }

        val botUsername = "Virexprobot"

        try {
            val intent =
                    Intent(
                            Intent.ACTION_VIEW,
                            Uri.parse("tg://resolve?domain=$botUsername&start=buy_$plan")
                    )
            startActivity(intent)
        } catch (e: Exception) {
            val intent =
                    Intent(
                            Intent.ACTION_VIEW,
                            Uri.parse("https://t.me/$botUsername?start=buy_$plan")
                    )
            startActivity(intent)
        }
    }

    override fun onResume() {
        super.onResume()
        // Обновляем при возврате из Telegram
        refreshSubscription()
    }
}
