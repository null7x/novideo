package com.virex.pro.network

import com.virex.pro.data.AuthResponse
import com.virex.pro.data.PreferencesManager
import com.virex.pro.data.SubscriptionInfo
import com.virex.pro.data.TemplatesResponse
import java.util.concurrent.TimeUnit
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.ResponseBody
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*

interface VirexApi {

    @GET("api/health") suspend fun healthCheck(): Response<Map<String, Any>>

    @POST("api/auth/deeplink")
    suspend fun authDeeplink(@Body body: Map<String, String>): Response<AuthResponse>

    @GET("api/user/subscription")
    suspend fun getSubscription(
            @Header("X-User-Id") userId: String,
            @Header("X-Auth-Token") token: String
    ): Response<SubscriptionInfo>

    @GET("api/templates") suspend fun getTemplates(): Response<TemplatesResponse>

    @Multipart
    @POST("api/video/process")
    suspend fun processVideo(
            @Header("X-User-Id") userId: String,
            @Header("X-Auth-Token") token: String,
            @Part video: MultipartBody.Part,
            @Part template: MultipartBody.Part,
            @Part text: MultipartBody.Part?
    ): Response<ResponseBody>

    @Multipart
    @POST("api/video/info")
    suspend fun getVideoInfo(
            @Header("X-User-Id") userId: String,
            @Header("X-Auth-Token") token: String,
            @Part video: MultipartBody.Part
    ): Response<Map<String, Any>>
}

class ApiClient(private val preferencesManager: PreferencesManager) {

    private val okHttpClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
                .connectTimeout(60, TimeUnit.SECONDS) // Увеличенный таймаут для подключения
                .readTimeout(15, TimeUnit.MINUTES) // Длинный таймаут для обработки видео
                .writeTimeout(15, TimeUnit.MINUTES)
                .retryOnConnectionFailure(true) // Автоматический retry при ошибке
                .addInterceptor { chain ->
                    val request = chain.request()
                    var lastException: Exception? = null

                    // Retry до 3 раз только при сетевых ошибках
                    for (attempt in 1..3) {
                        try {
                            val response = chain.proceed(request)
                            // Возвращаем любой ответ от сервера (даже 4xx/5xx)
                            return@addInterceptor response
                        } catch (e: java.net.ConnectException) {
                            lastException = e
                            android.util.Log.w(
                                    "ApiClient",
                                    "Connect attempt $attempt failed: ${e.message}"
                            )
                            if (attempt < 3) Thread.sleep(1000L * attempt)
                        } catch (e: java.net.SocketTimeoutException) {
                            lastException = e
                            android.util.Log.w(
                                    "ApiClient",
                                    "Timeout attempt $attempt: ${e.message}"
                            )
                            if (attempt < 3) Thread.sleep(1000L * attempt)
                        } catch (e: Exception) {
                            // Другие ошибки - не retry
                            throw e
                        }
                    }

                    throw (lastException
                            ?: java.io.IOException("Connection failed after 3 attempts"))
                }
                .addInterceptor(
                        HttpLoggingInterceptor().apply {
                            level = HttpLoggingInterceptor.Level.BASIC
                        }
                )
                .build()
    }

    val api: VirexApi by lazy {
        Retrofit.Builder()
                .baseUrl(preferencesManager.serverUrl + "/") // Ensure trailing slash
                .client(okHttpClient)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(VirexApi::class.java)
    }

    fun updateBaseUrl(newUrl: String) {
        preferencesManager.serverUrl = newUrl
    }
}
