package com.virex.pro.data

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit

class PreferencesManager(context: Context) {

    private val prefs: SharedPreferences =
            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    var userId: Long
        get() = prefs.getLong(KEY_USER_ID, 0)
        set(value) = prefs.edit { putLong(KEY_USER_ID, value) }

    var authToken: String?
        get() = prefs.getString(KEY_AUTH_TOKEN, null)
        set(value) = prefs.edit { putString(KEY_AUTH_TOKEN, value) }

    var username: String?
        get() = prefs.getString(KEY_USERNAME, null)
        set(value) = prefs.edit { putString(KEY_USERNAME, value) }

    var firstName: String?
        get() = prefs.getString(KEY_FIRST_NAME, null)
        set(value) = prefs.edit { putString(KEY_FIRST_NAME, value) }

    var isPremium: Boolean
        get() = prefs.getBoolean(KEY_IS_PREMIUM, false)
        set(value) = prefs.edit { putBoolean(KEY_IS_PREMIUM, value) }

    var subscriptionExpires: Long
        get() = prefs.getLong(KEY_SUBSCRIPTION_EXPIRES, 0)
        set(value) = prefs.edit { putLong(KEY_SUBSCRIPTION_EXPIRES, value) }

    var totalVideos: Int
        get() = prefs.getInt(KEY_TOTAL_VIDEOS, 0)
        set(value) = prefs.edit { putInt(KEY_TOTAL_VIDEOS, value) }

    var lastTemplate: String
        get() = prefs.getString(KEY_LAST_TEMPLATE, "tiktok") ?: "tiktok"
        set(value) = prefs.edit { putString(KEY_LAST_TEMPLATE, value) }

    var serverUrl: String
        get() = prefs.getString(KEY_SERVER_URL, DEFAULT_SERVER_URL) ?: DEFAULT_SERVER_URL
        set(value) = prefs.edit { putString(KEY_SERVER_URL, value) }

    val isLoggedIn: Boolean
        get() = userId > 0 && !authToken.isNullOrEmpty()

    fun logout() {
        prefs.edit {
            remove(KEY_USER_ID)
            remove(KEY_AUTH_TOKEN)
            remove(KEY_USERNAME)
            remove(KEY_FIRST_NAME)
            remove(KEY_IS_PREMIUM)
            remove(KEY_SUBSCRIPTION_EXPIRES)
        }
    }

    companion object {
        private const val PREFS_NAME = "virex_prefs"
        private const val KEY_USER_ID = "user_id"
        private const val KEY_AUTH_TOKEN = "auth_token"
        private const val KEY_USERNAME = "username"
        private const val KEY_FIRST_NAME = "first_name"
        private const val KEY_IS_PREMIUM = "is_premium"
        private const val KEY_SUBSCRIPTION_EXPIRES = "subscription_expires"
        private const val KEY_TOTAL_VIDEOS = "total_videos"
        private const val KEY_LAST_TEMPLATE = "last_template"
        private const val KEY_SERVER_URL = "server_url"

        // Локальный сервер для тестирования (замените на реальный URL для production)
        const val DEFAULT_SERVER_URL = "http://10.94.216.104:8080"
    }
}
