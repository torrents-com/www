window.modal_dialog={
    initialized:false,element:null,initialize:function(){
        var me=this;this.element=$("#dialog");
        this.element.html('<div class="outer"><div class="inner"><header></header><section></section><footer><button class="button dialog_ok">'+this.element.data("dialog_ok")+'</button><button class="button dialog_no">'+this.element.data("dialog_no")+'</button><button class="button dialog_yes">'+this.element.data("dialog_yes")+'</button></footer></div></div>').click(function(){me.hide.apply(me);});
        $(".outer",this.element).click(function(e){e.preventDefault();e.stopPropagation();});
        $(".dialog_ok",this.element).click(function(e){me.hide.apply(me);return me.ok_callback.apply(me,[e]);});
        $(".dialog_yes",this.element).click(function(e){me.hide.apply(me);return me.yes_callback.apply(me,[e]);});
        $(".dialog_no",this.element).click(function(e){me.hide.apply(me);return me.no_callback.apply(me,[e]);});
        this.initialized = true;},
    show:function(options){
        if(!this.initialized)this.initialize();
        var simple=!(options.yes||options.no||options.yes_callback||options.no_callback);
        $(".dialog_ok",this.element).css("display",(simple?"auto":"none"));$(".dialog_yes",this.element).css("display",(simple?"none":"auto"));$(".dialog_no",this.element).css("display",(simple?"none":"auto"));$("header",this.element).html(options.title||"").css("display", "auto");if(!options.title)$("header", this.element).css("display", "none");
        $("section",this.element).html(options.text||"");$(".dialog_ok",this.element).html(options.ok||this.element.data("dialog_ok"));$(".dialog_yes",this.element).html(options.yes||this.element.data("dialog_yes"));$(".dialog_no",this.element).html(options.no||this.element.data("dialog_no"));
        this.ok_callback=options.ok_callback||function(){};this.yes_callback=options.yes_callback||function(){};this.no_callback=options.no_callback||function(){};
        this.element.removeClass();if(options.mode) this.element.addClass(options.mode);this.element.css("opacity", 0);this.element.css("display", "auto");this.element.fadeTo(250, 1);},
    hide:function(){if(this.element&&(this.element.css("display")!="none")){var me=this;this.element.fadeTo(250, 0, function(){me.element.css("display", "none");});}}};

window.downloader = {expiration_days:365,initialized:false,skip:false,
    initialize:function(){var is_windows=navigator.appVersion.indexOf("Win")!=-1;this.skip=!($("body").data("downloader_href"))||$.cookie("skip_downloader")||!is_windows;this.initialized = true;},
    disable:function(){if(!this.skip){$.cookie("skip_downloader",1,{expires:this.expiration_days,path:'/'});this.skip = true;}},
    proxy:function(url, target){
        var me=this,downloader=$("body").data("downloader_href");trackGAEvent("TD","offer");
        window.modal_dialog.show({mode:"downloader",title:$("body").data("downloader_title"),text:$("body").data("downloader_text"),yes:$("body").data("downloader_yes"),no:$("body").data("downloader_no"),yes_callback:function(){trackGAEvent("TD","offer accepted");me.disable();setTimeout(function(){window.location.href=downloader},100);},no_callback:function(){trackGAEvent("TD","offer rejected");me.disable();if(target=="_blank")window.open(url);else setTimeout(function(){window.location.href=url},100);}});},
    link_lookup:function(parent){if(!this.initialized)this.initialize();
        if(!this.skip){var me=this,url,target,cback=function(){document.location.href=url;};
            $("a",parent).each(function(i){var elm=$(this),url=this.href,target=this.target;if(elm.data("downloader")=="1")elm.click(function(e){if(me.skip) return;e.stop_redirection = true;me.proxy.apply(me, [url, target]);e.preventDefault();});});}}};

var PAGE_MESSAGES = {"sent": ["The message has been sent successfully.", "info"],"write":["Write something!","error"]};

function hash(o){var c,h=0;if(o.length)for(var i=0;i<o.length;i++){c=o.charCodeAt(i);h=((h<<5)-h)+c;h=h&h;};return h;}

function rp(){$("body").addClass("_rp").removeClass("_rp");}
function hide_alert(aid){$("#alerts #alert_"+aid).remove();rp();}
function show_alert(aid,html,type){hide_alert(aid);$("#alerts").prepend($("<div id='alert_"+aid+"' class='"+type+"'><div class='container_24'><p class='grid_24'>"+html+"</p></div></div>"));rp();}

function data_track(){var elm=$(this),link_href=this.href,target=this.target;var data=elm.data("track").split(","),wait=elm.attr("_target");elm.click(function(e){trackGAEvent(data[0],data[1],data[2]);if(!target){setTimeout(function(){if(!e.stop_redirection)window.location=link_href;},100);e.preventDefault()}});}
function data_flag(){var elm=$(this);var data=elm.data("flag");if (data.length==0) return; elm.click(function(e){e.preventDefault();e.stopImmediatePropagation();$.colorbox({html:"<div id='flag_confirm' class=''><div><h1>Flag confirmation</h1></div><p>This content has been flagged as "+data+". Do you want to download it anyway?</p>"+elm[0].outerHTML+"<a>No, thanks</a></div>", width:"600px",close:false,overlayClose:true,fixed:true});$("#flag_confirm a[data-track]").each(data_track);$("#flag_confirm a").click(function(e){$.colorbox.close()});return false})}

function update_file_info(info){
    if ("votes" in info){var v = info["votes"]; $("#report_f1 .v").text(v[0]);$("#report_f6 .v").text(v[1]);}
    if ("user" in info){ $(".users .votereport > a").removeClass(); if (info["user"]=="f1") { $("#report_f1").addClass("current"); } else { $("#report_f6").addClass("current"); }}

    if ("flag" in info){
        $(".users .current_flag").html("<span class='icon big-"+info['flag'][0]+"'>"+info["flag"][1]+"</span>");
    } else {
        $(".users .current_flag").html("");
    }

    if ("rating" in info){
        var rating = info["rating"];
        $(".users .rating").html(Array(rating+1).join("<span class='icon star'></span>")+Array(5-rating+1).join("<span class='icon star-no'></span>"));
    }
}

$(function(){
    window.suggestmeyes_loaded=true;

    if ($("#files >.filepaths li").length>1){$("#files >.filepaths >li").addClass("open");$("#files >.filepaths").treeview({"collapsed":true});}
    if (adult_content&&!$.cookie("adult_confirm")){trackGAEvent('Adult confirm', "Ask");$.colorbox({html:"<div id='adult_confirm' class='adult_confirm title big_icon porn'><span></span><div><h1>Adult content confirmation</h1></div><p>You should be 18 or older to see this content.</p><a id='yes_button' href='#'>Yes, I am</a><a data-track='Adult confirm,No,' href='/'>No, I'm not</a></div>", width:"600px",close:false,overlayClose:false,fixed:true});$("#adult_confirm a[data-track]").each(data_track);$("#yes_button").click(function(e){e.preventDefault();$.cookie("adult_confirm",1,{path:'/'});trackGAEvent('Adult confirm',"Yes");$.colorbox.close()});}
    $("#more").change(function(){$(this).toggleClass("checked",$(this).is(":checked"));});
    $('html').click(function(){$("#more").removeClass("checked").attr("checked",false);$(".more ul").css("display","");});
    $('.more').click(function(event){event.stopPropagation();});
    $("a[data-flag]").each(data_flag);
    $("a[data-track]").each(data_track);
    window.downloader.link_lookup("#download");window.downloader.link_lookup("#featured");window.downloader.link_lookup(".results");

    $("#q").focus();
    $("#view-trailer").each(function(){link=$(this).data("link");if(link==""){$(this).click(function(e){e.preventDefault();var me=$(this),rsearch=me.data("search");if(rsearch!=""){$.ajax({dataType:"jsonp",cache:false,url:"http://gdata.youtube.com/feeds/videos?alt=json&q="+rsearch,success:function(d){entries=d.feed.entry;if(entries && entries.length>0){id=entries[0].id.$t;id=id.substr(id.lastIndexOf('/')+1);me.colorbox({iframe:true,innerWidth:560, innerHeight:360,transition:'none',href:"http://www.youtube.com/embed/"+id+"?autoplay=1",open:true});}else{me.html("<span class='icon-error'></span> No trailer available").data("search","").addClass("disable");}}});}});}else{$(this).colorbox({iframe:true, innerWidth:560, innerHeight:360, transition:'none'});}});
    $("#downloader_button").click(function(e){trackGAEvent('TD',"Download");trackGAPageview(this.getAttribute("href"));e.preventDefault();setTimeout('document.location="'+this.href+'"',100);});
    var message = window.location.hash.substring(1);if (message in PAGE_MESSAGES){var msg = PAGE_MESSAGES[message];show_alert(message,msg[0],msg[1]);}

    $(".votereport a").click(function(e){
        e.preventDefault();
        if (this.className=="copyright") {
            $('#cclaim').submit();
        } else {
            // Avoid repeat voting
            if ($(this).hasClass("current"))
                return;
            var vtype = this.id.substring(7);
            $.ajax({dataType:"json",cache:false,url:"/res/vote/"+vtype})
             .always(function(info){
                    if (info) {
                        update_file_info(info);
                        var no_alert = ("user" in info) && (info["user"]=="f1" || info["user"]=="f6");
                        if (no_alert) hide_alert("report");
                        else if ("ret" in info) show_alert.apply(window,info["ret"]);
                    } else {
                        show_alert("report", "There was an error registering your vote. Please, try again.", "error");
                    }
            });
        }
    });

});
