package com.virex.pro

import android.app.Application
import com.virex.pro.data.PreferencesManager
import com.virex.pro.network.ApiClient

class VirexApp : Application() {
    
    lateinit var preferencesManager: PreferencesManager
    lateinit var apiClient: ApiClient
    
    override fun onCreate() {
        super.onCreate()
        instance = this
        
        preferencesManager = PreferencesManager(this)
        apiClient = ApiClient(preferencesManager)
    }
    
    companion object {
        lateinit var instance: VirexApp
            private set
    }
}
