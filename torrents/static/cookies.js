;(function($){$.cookiesLaw={new_cid:false,cid:false,notified:false,hide_msg:false,start_scripts:false,
    gen_id:function(){this.new_cid=true;var c=navigator.appName+navigator.version+navigator.platform+navigator.userAgent+(navigator.cookie?navigator.cookie:"")+(document.referrer?document.referrer:"");d=c.length;for(var e=window.history.length;0<e;)c+=e--^d++;this.cid=(Math.round(2147483647*Math.random())^hash(c)&2147483647)+"."+(Math.round((new Date)["getTime"]()/1E3));},
    run_scripts:function(){if(!this.start_scripts)return;if(this.new_cid){this.new_cid=false;$.cookie("__cid",this.cid,{expires:730,path:'/'});}this.start_scripts=false;this.start_scripts();},
    initialize:function(ds,ss){this.cid=$.cookie("__cid")||this.gen_id();this.start_scripts=ss;this.domains=ds;var cookie_level=$.cookie("cookie_level");this.notified=cookie_level>0;this.hide_msg=cookie_level>1;if (this.notified){this.final_process();return;}this.visit_domains("notify", function(){$.cookie("cookie_level", $.cookiesLaw.hide_msg?2:1,{expires:3650,path:'/'});$.cookiesLaw.final_process();});},
    visit_domains:function(ac,af){var rs=[];for(var i=0;i<this.domains.length;i++){rs.push($.ajax({type:'GET',url:this.domains[i]+"?cid="this.cid+"&"+ac,async:true,contentType:"application/json",dataType:'jsonp',success:function(r){if (r>0){$.cookiesLaw.notified=true;if(r>1){$.cookiesLaw.hide_msg=true;}}}}));}$.when.apply($,rs).done(af);},
    final_process:function(){if(this.notified){this.run_scripts();}if(!this.hide_msg){if(this.notified)trackGAEvent('CookieLaw', "Notified");$(function(){show_alert("cookies", "<a href='#' id='cookies_accept'>cerrar</a>Utilizamos cookies propias y de terceros para mejorar nuestros servicios y realizar estadísticas sobre el uso de nuestra web.<br/>Si continua navegando, consideramos que acepta su uso. Puede cambiar la configuración u obtener más información <a id='cookies_info' href='#'>aquí</a>.", "info");$("#cookies_accept").click(function(e){e.preventDefault();$.cookie("cookie_level",2,{expires:3650,path:'/'});$.cookiesLaw.visit_domains("accept",function(){$.cookiesLaw.run_scripts();trackGAEvent('CookieLaw',"Close");hide_alert("cookies");});});$("#cookies_info").click(function(e){e.preventDefault();$.cookiesLaw.showMoreInfo();});});}},
    showMoreInfo:function(){$.colorbox({href:"/static/cookies.htm",height:"80%",width:"80%",close:"cerrar",fixed:true});}};})(jQuery);







