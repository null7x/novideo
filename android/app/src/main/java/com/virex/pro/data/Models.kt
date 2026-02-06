package com.virex.pro.data

data class Template(
        val id: String,
        val name: String,
        val description: String,
        val icon: Int = 0,
        val isPremium: Boolean = false
)

data class AuthResponse(
        val success: Boolean,
        val token: String?,
        val user: UserInfo?,
        val subscription: SubscriptionInfo?,
        val error: String?
)

data class UserInfo(val id: Long, val username: String?, val first_name: String?)

data class SubscriptionInfo(
        val is_premium: Boolean,
        val plan: String? = "free",
        val subscription: SubscriptionDetails?,
        val videos_today: Int = 0,
        val total_videos: Int = 0,
        val daily_limit: Int = 3,
        val max_file_size: Int = 100
)

data class SubscriptionDetails(val type: String?, val expires: Long?)

data class TemplatesResponse(
        val templates: List<TemplateItem>,
        val categories: List<CategoryItem>? = null
)

data class TemplateItem(
        val id: String,
        val name: String,
        val description: String,
        val category: String? = null,
        val isPremium: Boolean = false,
        val effects: List<String>? = null
)

data class CategoryItem(val id: String, val name: String)

data class ProcessingState(
        val status: ProcessingStatus,
        val progress: Int = 0,
        val message: String = "",
        val outputPath: String? = null,
        val error: String? = null
)

enum class ProcessingStatus {
    IDLE,
    UPLOADING,
    PROCESSING,
    DOWNLOADING,
    COMPLETED,
    ERROR
}
